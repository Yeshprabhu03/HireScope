import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
import os

from config import settings

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

# In-memory job store (replace with DB in production)
jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("HireScope API starting up...")
    yield
    logger.info("HireScope API shutting down...")


app = FastAPI(
    title="HireScope API",
    description="AI-powered job intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
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


class RAGQueryRequest(BaseModel):
    query: str
    company: Optional[str] = None
    role: Optional[str] = None
    limit: int = 5


async def run_analysis(job_id: str, job_url: str):
    """Background task: run the full LangGraph analysis pipeline."""
    try:
        jobs[job_id]["status"] = "processing"
        logger.info(f"Starting analysis for job_id={job_id}, url={job_url}")

        from agents.orchestrator import run_job_analysis

        result = await run_job_analysis(job_id=job_id, job_url=job_url, jobs=jobs)

        jobs[job_id].update(
            {
                "status": "completed",
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
        logger.info(f"Analysis completed for job_id={job_id}")

    except Exception as e:
        logger.error(f"Analysis failed for job_id={job_id}: {e}", exc_info=True)
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
        "error": None,
        "progress": {
            "current_step": "queued",
            "current_step_label": "⏳ Queued for analysis...",
            "completed_steps": [],
            "total_steps": 6,
            "percent": 0,
        },
    }
    background_tasks.add_task(run_analysis, job_id, request.job_url)
    logger.info(f"Created job_id={job_id} for url={request.job_url}")
    return {"job_id": job_id, "status": "created"}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status and metadata for a specific job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    return {
        "job_id": job_id,
        "job_url": job.get("job_url"),
        "status": job.get("status"),
        "error": job.get("error"),
        "parsed_jd": job.get("parsed_jd"),
        "progress": job.get("progress"),
    }


@app.get("/api/jobs/{job_id}/report")
async def get_job_report(job_id: str):
    """Get the full HTML report for a completed job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    if job.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed yet. Current status: {job.get('status')}",
        )
    return {
        "job_id": job_id,
        "html_report": job.get("html_report"),
        "parsed_jd": job.get("parsed_jd"),
        "company_intelligence": job.get("company_intelligence"),
        "salary_intelligence": job.get("salary_intelligence"),
        "interview_intelligence": job.get("interview_intelligence"),
    }


@app.get("/api/jobs")
async def list_jobs():
    """List all analyzed jobs."""
    return [
        {
            "job_id": jid,
            "job_url": j.get("job_url"),
            "status": j.get("status"),
            "job_title": (j.get("parsed_jd") or {}).get("job_title"),
            "company": (j.get("parsed_jd") or {}).get("company"),
            "progress": j.get("progress"),
        }
        for jid, j in jobs.items()
    ]


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
