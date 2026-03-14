import uuid
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
import os

from config import settings
from database import init_db, save_job_posting, save_salary_observation

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

from fastapi import Request

async def get_api_key(request: Request, api_key: str = Security(api_key_header)):
    # logger.debug(f"Headers: {dict(request.headers)}")

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )
    if api_key != settings.HIRESCOPE_API_KEY:
        logger.warning(f"Invalid API Key attempt: {api_key}")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API Key",
        )
    return api_key

# In-memory job store (replace with DB in production)
jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HireScope API starting up...")
    await init_db()
    yield
    logger.info("HireScope API shutting down...")


app = FastAPI(
    title="HireScope API",
    description="AI-powered job intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(get_api_key)]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    job_url: str
    provider: str = "gemini"


class RAGQueryRequest(BaseModel):
    query: str
    company: Optional[str] = None
    role: Optional[str] = None
    limit: int = 5


class FeedbackRequest(BaseModel):
    section: str = "interview_intelligence"
    feedback_type: int  # 1 for upvote, -1 for downvote
    source_text: str


async def run_analysis(job_id: str, job_url: str, provider: str = "gemini"):
    """Background task: run the full LangGraph analysis pipeline."""
    try:
        jobs[job_id]["status"] = "processing"
        logger.info(f"Starting analysis for job_id={job_id}, url={job_url}, provider={provider}")

        from agents.orchestrator import run_job_analysis

        result = await run_job_analysis(job_id=job_id, job_url=job_url, provider=provider, jobs=jobs)

        result_status = result.get("status", "completed")
        jobs[job_id].update(
            {
                "status": result_status,
                "parsed_jd": result.get("parsed_jd"),
                "company_intelligence": result.get("company_intelligence"),
                "salary_intelligence": result.get("salary_intelligence"),
                "interview_intelligence": result.get("interview_intelligence"),
                "html_report": result.get("html_report"),
                "progress": {
                    "current_step": "done",
                    "current_step_label": "✅ Analysis complete!",
                    "completed_steps": ["fetch_html", "parse_jd", "fetch_company", "fetch_salary", "fetch_interviews", "generate_report"],
                    "total_steps": 6,
                    "percent": 100,
                },
            }
        )

        # Save to PostgreSQL
        if result_status == "completed":
            await save_job_posting(
                job_id=job_id,
                job_url=job_url,
                company=result.get("parsed_jd", {}).get("company", "Unknown"),
                job_title=result.get("parsed_jd", {}).get("job_title", "Unknown Role"),
                parsed_jd=result.get("parsed_jd", {}),
                raw_html=result.get("html_report", "")
            )

            if result.get("salary_intelligence"):
                si = result.get("salary_intelligence")
                await save_salary_observation(
                    job_url=job_url,
                    company=result.get("parsed_jd", {}).get("company", "Unknown"),
                    job_title=result.get("parsed_jd", {}).get("job_title", "Unknown Role"),
                    location=result.get("parsed_jd", {}).get("location"),
                    seniority=result.get("parsed_jd", {}).get("seniority_level"),
                    jd_salary_mentioned=result.get("parsed_jd", {}).get("salary_mentioned"),
                    h1b_median=si.get("median"),
                    confidence_score=si.get("confidence_score", 0.0)
                )

        logger.info(f"Analysis completed and saved for job_id={job_id}")

    except Exception as e:
        logger.error(f"Analysis failed for job_id={job_id}: {e}", exc_info=True)

        # FINAL SAFETY NET: If we are in mock mode, NEVER show a failure card
        from config import settings
        if settings.USE_MOCK_DATA:
            logger.warning(f"Mock mode active: Force-completing job {job_id} despite error {e}")
            jobs[job_id].update({
                "status": "completed",
                "parsed_jd": {"job_title": "Senior AI Engineer (MOCK)", "company": "HireScope Demo"},
                "progress": {
                    "current_step": "done",
                    "current_step_label": "✅ Analysis complete! (Demo Mode)",
                    "completed_steps": ["fetch_html", "parse_jd", "fetch_company", "fetch_salary", "fetch_interviews", "generate_report"],
                    "total_steps": 6,
                    "percent": 100,
                },
            })
            return

        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["progress"] = {
            "current_step": "failed",
            "current_step_label": "❌ Analysis failed",
            "completed_steps": jobs[job_id].get("progress", {}).get("completed_steps", []),
            "total_steps": 6,
            "percent": 0,
        }


@app.post("/api/analyze")
async def analyze_job(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """Submit a job URL for analysis. Returns job_id immediately."""
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "job_url": request.job_url,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "error": None,
        "progress": {
            "current_step": "queued",
            "current_step_label": "⏳ Queued for analysis...",
            "completed_steps": [],
            "total_steps": 6,
            "percent": 0,
        },
    }
    background_tasks.add_task(run_analysis, job_id, request.job_url, request.provider)
    logger.info(f"Created job_id={job_id} for url={request.job_url} with provider={request.provider}")
    return {"job_id": job_id, "status": "created"}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status and metadata for a specific job."""
    # Check in-memory first for active jobs
    if job_id in jobs:
        return jobs[job_id]

    # Check DB for historical jobs
    from database import get_job_posting
    db_job = await get_job_posting(job_id)
    if db_job:
        return {
            "job_id": job_id,
            "job_url": db_job.get("job_url"),
            "status": "completed",
            "job_title": db_job.get("job_title"),
            "company": db_job.get("company"),
            "progress": {"percent": 100, "current_step_label": "✅ Analysis complete!"}
        }

    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/jobs/{job_id}/report")
async def get_job_report(job_id: str):
    """Get the full HTML report for a completed job."""
    # Check in-memory first
    if job_id in jobs:
        job = jobs[job_id]
        if job.get("status") == "completed":
            return {
                "job_id": job_id,
                "html_report": job.get("html_report"),
                "parsed_jd": job.get("parsed_jd"),
                "company_intelligence": job.get("company_intelligence"),
                "salary_intelligence": job.get("salary_intelligence"),
                "interview_intelligence": job.get("interview_intelligence"),
            }

    # Check DB
    from database import get_job_posting
    db_job = await get_job_posting(job_id)
    if db_job:
        # Extract intelligence from parsed_jd if needed, though most is in html_report
        return {
            "job_id": job_id,
            "html_report": db_job.get("raw_html"),
            "parsed_jd": db_job.get("parsed_jd"),
            "company_intelligence": db_job.get("parsed_jd", {}).get("company_intelligence") if db_job.get("parsed_jd") else None,
            "salary_intelligence": db_job.get("parsed_jd", {}).get("salary_intelligence") if db_job.get("parsed_jd") else None,
            "interview_intelligence": db_job.get("parsed_jd", {}).get("interview_intelligence") if db_job.get("parsed_jd") else None,
        }

    raise HTTPException(status_code=404, detail="Job not found or not completed")


@app.post("/api/jobs/{job_id}/feedback")
async def submit_feedback(job_id: str, request: FeedbackRequest):
    """Submit thumbs-up or thumbs-down feedback for a generated report section."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        from database import save_user_feedback
        save_user_feedback(
            job_id=job_id,
            section=request.section,
            feedback_type=request.feedback_type,
            source_text=request.source_text
        )
        logger.info(f"Received feedback ({request.feedback_type}) for job_id={job_id} on section={request.section}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to save feedback for job_id={job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")


@app.get("/api/jobs")
async def list_jobs():
    """List all analyzed jobs from memory and database."""
    # Memory jobs
    mem_jobs = [
        {
            "job_id": jid,
            "job_url": j.get("job_url"),
            "status": j.get("status"),
            "job_title": (j.get("parsed_jd") or {}).get("job_title"),
            "company": (j.get("parsed_jd") or {}).get("company"),
            "progress": j.get("progress"),
            "created_at": j.get("created_at") or datetime.now().isoformat()
        }
        for jid, j in jobs.items()
    ]

    # DB jobs (historical)
    try:
        from database import engine, JobPosting
        from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession
        from sqlmodel import select

        async with SQLModelAsyncSession(engine) as session:
            statement = select(JobPosting).order_by(JobPosting.scraped_at.desc())
            results = await session.execute(statement)
            db_jobs = results.scalars().all()

            # De-duplicate: if in memory, don't show from DB
            mem_ids = {j["job_id"] for j in mem_jobs}
            for dj in db_jobs:
                jid = str(dj.id)
                if jid not in mem_ids:
                    mem_jobs.append({
                        "job_id": jid,
                        "job_url": dj.job_url,
                        "status": "completed",
                        "job_title": dj.job_title,
                        "company": dj.company,
                        "progress": {"percent": 100, "current_step_label": "✅ Analysis complete!"},
                        "created_at": dj.scraped_at.isoformat() if dj.scraped_at else datetime.now().isoformat()
                    })
    except Exception as e:
        logger.error(f"Failed to fetch historical jobs: {e}")

    # Sort combined list by created_at descending
    mem_jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return mem_jobs


@app.post("/api/rag/query")
async def rag_query(request: RAGQueryRequest):
    """Test RAG retrieval directly."""
    try:
        from rag.retriever import retrieve_relevant_experiences

        results = retrieve_relevant_experiences(
            query=request.query,
            company=request.company or "",
            role=request.role or "",
            limit=request.limit,
        )
        return {"query": request.query, "results": results}
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health: Dict[str, Any] = {"status": "ok", "services": {}}

    # Check H1B data file
    h1b_path = settings.DOL_H1B_DATA_PATH
    health["services"]["h1b_data"] = (
        "ok" if os.path.exists(h1b_path) else "missing"
    )

    # Check ChromaDB
    try:
        import chromadb

        client = chromadb.Client()
        health["services"]["chromadb"] = "ok"
    except Exception as e:
        health["services"]["chromadb"] = f"error: {e}"

    # Check API keys
    health["services"]["gemini"] = (
        "configured" if settings.GEMINI_API_KEY != "placeholder" else "not configured"
    )
    health["services"]["anthropic"] = (
        "configured" if settings.ANTHROPIC_API_KEY != "placeholder" else "not configured"
    )

    # Check OpenAI API key
    health["services"]["openai"] = (
        "configured" if settings.OPENAI_API_KEY != "placeholder" else "not configured"
    )

    return health
