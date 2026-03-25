"""
Job Analysis Orchestrator: runs the analysis pipeline as an Agentic State Machine using LangGraph.
"""
import asyncio
import logging
from typing import TypedDict, Optional, List, Annotated, Dict, Any
import operator

from langgraph.graph import StateGraph, END
import enum

logger = logging.getLogger(__name__)


class HireScopeState(TypedDict):
    """Explicitly typed state for the HireScope analysis pipeline."""
    # Core job identification
    job_id: str
    job_url: str

    # Content and analysis
    html_content: str
    text_content: str
    parsed_jd: Optional[Dict[str, Any]]
    sub_team: Optional[str]
    extracted_team_context: Optional[str]

    # Intelligence results
    company_intelligence: Optional[Dict[str, Any]]
    salary_intelligence: Optional[Dict[str, Any]]
    interview_intelligence: Optional[Dict[str, Any]]

    # Final output and status
    html_report: str
    status: str
    error: str

    # Configuration
    use_mock: bool
    provider: str
    model_display_name: str

    # Execution control
    browser_retried: bool
    is_upload: bool


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def fetch_html_node(state: HireScopeState) -> dict:
    """Fetch HTML from the job URL and return content."""
    job_id = state.get("job_id", "unknown")
    job_url = state.get("job_url", "")
    use_mock = state.get("use_mock", False)

    logger.info(f"[{job_id}] Fetching HTML from {job_url} (mock={use_mock})")

    from utils.job_fetcher import get_job_content

    if state.get("is_upload"):
        logger.info(f"[{job_id}] Bypassing fetch for PDF upload")
        return {"status": "fetched"}

    try:
        html, text = get_job_content(job_url, use_mock=use_mock)
        logger.info(f"[{job_id}] Successfully fetched {len(html)} bytes")
        return {"html_content": html, "text_content": text, "status": "fetched"}
    except Exception as e:
        logger.error(f"[{job_id}] Fetch error: {e}")
        return {"status": "failed", "error": str(e)}


async def parse_jd_node(state: HireScopeState) -> dict:
    """Parse job description."""
    if state.get("parsed_jd") and state.get("status") == "parsed":
        logger.info(f"[{state['job_id']}] Skipping JD parsing (loaded from cache)")
        return {}

    logger.info(f"[{state['job_id']}] Parsing job description")
    try:
        from agents.jd_parser import parse_job_description

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        parsed = await parse_job_description(state["html_content"], use_mock=use_mock, provider=provider)
        parsed_dict = parsed.model_dump()

        # If it looks like a career page, mark as failed
        if parsed_dict.get("page_type") == "career_page":
            jobs_found = ", ".join(parsed_dict.get("detected_jobs", []))
            error_msg = f"This looks like a careers listing page, not a specific job posting. I found these jobs: {jobs_found}. Please provide a direct link to one of them."
            return {"parsed_jd": parsed_dict, "status": "failed", "error": error_msg}

        return {
            "parsed_jd": parsed_dict,
            "sub_team": parsed_dict.get("sub_team"),
            "extracted_team_context": parsed_dict.get("extracted_team_context"),
            "status": "parsed"
        }
    except Exception as e:
        logger.error(f"parse_jd_node failed: {e}", exc_info=True)
        if state.get("use_mock"):
             return {
                "parsed_jd": {"job_title": "Senior AI Engineer", "company": "Antigravity AI", "location": "Remote", "seniority_level": "senior", "required_skills": ["Python", "Transformers", "LangGraph"]},
                "status": "parsed"
             }
        return {
            "parsed_jd": {"job_title": "Unknown", "company": "Unknown", "location": "Unknown"},
            "status": "failed",
            "error": str(e),
        }


async def browser_retry_node(state: HireScopeState) -> dict:
    """Auto-Fixing Agent: retry fetching with in-process async Playwright (no subprocess overhead)."""
    logger.warning(f"[{state['job_id']}] Triggering Auto-Fixing Agent with in-process Browser...")
    try:
        from utils.browser_fetch import fetch_rendered_text
        import asyncio
        # Run with a 45s timeout — same as old subprocess timeout, but no interpreter cold-start
        html = await asyncio.wait_for(fetch_rendered_text(state["job_url"]), timeout=45)
        if html and len(html.strip()) > 500:
            logger.info(f"[{state['job_id']}] In-process browser fetch successful!")
            return {
                "html_content": html,
                "browser_retried": True,
                "status": "fetched"
            }
        else:
            logger.warning(f"[{state['job_id']}] In-process browser returned insufficient content")
            return {"browser_retried": True}
    except Exception as fix_err:
        logger.error(f"In-process browser fetch failed: {fix_err}")
        return {"browser_retried": True}


async def fetch_company_node(state: HireScopeState) -> dict:
    """Fetch company intelligence."""
    jd = state.get("parsed_jd") or {}
    company = jd.get("company", "Unknown")
    job_title = jd.get("job_title", "Unknown Role")
    logger.info(f"[{state['job_id']}] Fetching company intel for '{company}' regarding '{job_title}'")

    try:
        from data_sources.company_intel import fetch_company_intel
        from database import get_company_snapshot, save_company_snapshot
        from datetime import datetime, timedelta

        cache_key = f"{company}::{job_title}"
        if company != "Unknown":
            cached_company = await get_company_snapshot(cache_key)
            if cached_company and cached_company.get("data"):
                snapshot_date_raw = cached_company.get("snapshot_date")
                if snapshot_date_raw:
                    snapshot_date = snapshot_date_raw if isinstance(snapshot_date_raw, datetime) else datetime.fromisoformat(snapshot_date_raw)
                    if datetime.now() - snapshot_date < timedelta(days=30):
                        return {"company_intelligence": cached_company["data"]}

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        sub_team = state.get("sub_team")
        team_seed = state.get("extracted_team_context")

        intel = await fetch_company_intel(
            company,
            role=job_title,
            parsed_jd=jd,
            sub_team=sub_team,
            team_context=team_seed,
            use_mock=use_mock,
            provider=provider
        )

        if company != "Unknown" and intel and not intel.get("error"):
            await save_company_snapshot(cache_key, intel)

        return {"company_intelligence": intel}
    except Exception as e:
        logger.error(f"fetch_company_node failed: {e}", exc_info=True)
        if state.get("use_mock"):
            return {"company_intelligence": {"name": company, "industry": "Artificial Intelligence", "mission": "Advancing agentic coding."}}
        return {"company_intelligence": {"name": company, "error": str(e)}}


async def fetch_salary_node(state: HireScopeState) -> dict:
    """Analyze salary data."""
    jd = state.get("parsed_jd") or {}
    logger.info(f"[{state['job_id']}] Analyzing salary for '{jd.get('job_title')}' at '{jd.get('company')}'")
    try:
        from agents.salary_agent import analyze_salary
        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        salary = await analyze_salary(
            job_title=jd.get("job_title", "Software Engineer"),
            company=jd.get("company", "Unknown"),
            location=jd.get("location", "Unknown"),
            seniority_level=jd.get("seniority_level", "mid"),
            required_skills=jd.get("required_skills", []),
            salary_mentioned=jd.get("salary_mentioned"),
            jd_text_snippet=jd.get("jd_text_snippet"),
            use_mock=use_mock,
            provider=provider,
        )
        return {"salary_intelligence": salary}
    except Exception as e:
        logger.error(f"fetch_salary_node failed: {e}", exc_info=True)
        return {"salary_intelligence": {"error": str(e), "estimated_range": "N/A"}}


async def fetch_interviews_node(state: HireScopeState) -> dict:
    """Fetch interview intelligence."""
    jd = state.get("parsed_jd") or {}
    company_intel = state.get("company_intelligence") or {}
    company = jd.get("company", "Unknown")
    role = jd.get("job_title", "Software Engineer")
    industry = company_intel.get("industry", "Technology")
    logger.info(f"[{state['job_id']}] Fetching interview intel for '{role}' at '{company}'")
    try:
        from agents.interview_agent import analyze_interviews
        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        intel = await analyze_interviews(
            job_title=role,
            company=company,
            industry=industry,
            parsed_jd=jd,
            company_intel=company_intel,
            jd_text_snippet=jd.get("jd_text_snippet"),
            use_mock=use_mock,
            provider=provider
        )
        return {"interview_intelligence": intel}
    except Exception as e:
        logger.error(f"fetch_interviews_node failed: {e}", exc_info=True)
        return {"interview_intelligence": {"error": str(e), "questions": []}}


async def parallel_intel_node(state: HireScopeState) -> dict:
    """
    Tier 2 optimization: run company intelligence and salary analysis in parallel.
    These two agents are fully independent — no reason to run them sequentially.
    Saves ~20-35 seconds per analysis.
    """
    logger.info(f"[{state['job_id']}] Running company + salary in PARALLEL")
    company_result, salary_result = await asyncio.gather(
        fetch_company_node(state),
        fetch_salary_node(state),
        return_exceptions=True
    )
    combined = {}
    if isinstance(company_result, dict):
        combined.update(company_result)
    else:
        logger.error(f"Company intel failed in parallel node: {company_result}")
        combined["company_intelligence"] = {"error": str(company_result)}

    if isinstance(salary_result, dict):
        combined.update(salary_result)
    else:
        logger.error(f"Salary analysis failed in parallel node: {salary_result}")
        combined["salary_intelligence"] = {"error": str(salary_result), "estimated_range": "N/A"}

    return combined


async def generate_report_node(state: HireScopeState) -> dict:
    """Generate final report."""
    logger.info(f"[{state['job_id']}] Generating HTML report")
    try:
        from output.report_gen import generate_html_report
        html = generate_html_report(
            parsed_jd=state.get("parsed_jd") or {},
            company_intel=state.get("company_intelligence") or {},
            salary_intel=state.get("salary_intelligence") or {},
            interview_intel=state.get("interview_intelligence") or {},
            job_id=state.get("job_id", ""),
            model_name=state.get("model_display_name", "AI Assistant"),
        )
        return {"html_report": html, "status": "completed"}
    except Exception as e:
        logger.error(f"generate_report_node failed: {e}", exc_info=True)
        # If mock mode is on, a failure in report gen shouldn't block the UI
        from config import settings
        if settings.USE_MOCK_DATA:
             from output.report_gen import generate_html_report
             html = generate_html_report(parsed_jd={}, company_intel={}, salary_intel={}, interview_intel={})
             return {"html_report": html, "status": "completed"}
        return {"html_report": "Error", "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def router(state: HireScopeState):
    """Router for conditional edges."""
    status = state.get("status")
    if status == "failed":
        return END

    # Check if we need retry
    parsed_jd = state.get("parsed_jd") or {}
    if (parsed_jd.get("company") == "Unknown" or parsed_jd.get("job_title") == "Unknown") and not state.get("browser_retried"):
        return "browser_retry"

    if status == "parsed":
        return "fetch_company"

    return END


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

workflow = StateGraph(HireScopeState)

# Define the workflow
workflow = StateGraph(HireScopeState)

workflow.add_node("fetch_html", fetch_html_node)
workflow.add_node("parse_jd", parse_jd_node)
workflow.add_node("browser_retry", browser_retry_node)
workflow.add_node("parallel_intel", parallel_intel_node)  # company + salary in parallel
workflow.add_node("fetch_interviews", fetch_interviews_node)
workflow.add_node("generate_report", generate_report_node)

workflow.set_entry_point("fetch_html")

# Define edges
workflow.add_edge("fetch_html", "parse_jd")

workflow.add_conditional_edges(
    "parse_jd",
    router,
    {
        "browser_retry": "browser_retry",
        "fetch_company": "parallel_intel",  # route to parallel node
        END: END
    }
)

workflow.add_edge("browser_retry", "parse_jd")
workflow.add_edge("parallel_intel", "fetch_interviews")  # interviews wait for both
workflow.add_edge("fetch_interviews", "generate_report")
workflow.add_edge("generate_report", END)

app = workflow.compile()


# ---------------------------------------------------------------------------
# Progress Tracking & Run Logic
# ---------------------------------------------------------------------------

PIPELINE_STEPS_LABELS = {
    "fetch_html": "🌐 Fetching job page...",
    "parse_jd": "📋 Parsing job description...",
    "browser_retry": "🕵️ Auto-Fixing (Browser)...",
    "fetch_company": "🏢 Gathering company intelligence...",
    "fetch_salary": "💰 Analyzing salary data...",
    "fetch_interviews": "🎯 Researching interview questions...",
    "generate_report": "📊 Generating your report...",
}

def _update_progress_live(jobs: dict, job_id: str, node_name: str, completed: list, total: int):
    if not jobs or job_id not in jobs:
        return
    label = PIPELINE_STEPS_LABELS.get(node_name, "Processing...")
    percent = int((len(completed) / total) * 100)
    jobs[job_id]["progress"] = {
        "current_step": node_name,
        "current_step_label": label,
        "completed_steps": list(completed),
        "total_steps": total,
        "percent": percent,
    }


async def run_job_analysis(job_id: str, job_url: str, provider: str = "gemini", jobs: dict = None, uploaded_text: str = None) -> dict:
    from config import settings

    def get_display_name(p):
        return {"gemini": "Gemini 2.0 Flash", "anthropic": "Claude 3.5 Sonnet", "openai": "GPT-4o"}.get(p, "AI Assistant")

    initial_state: JobAnalysisState = {
        "job_id": job_id,
        "job_url": job_url,
        "html_content": "",
        "text_content": "",
        "parsed_jd": None,
        "sub_team": None,
        "extracted_team_context": None,
        "company_intelligence": None,
        "salary_intelligence": None,
        "interview_intelligence": None,
        "html_report": "",
        "status": "starting",
        "error": "",
        "use_mock": settings.USE_MOCK_DATA,
        "provider": provider,
        "model_display_name": get_display_name(provider),
        "browser_retried": False,
        "is_upload": bool(uploaded_text)
    }

    if uploaded_text:
        initial_state["html_content"] = uploaded_text
        initial_state["text_content"] = uploaded_text

    final_state = initial_state
    completed = []
    total = len(PIPELINE_STEPS_LABELS)

    PIPELINE_TIMEOUT_SECONDS = 120 # Increased for LangGraph and potential retries

    try:
        # We use astream to capture node completions for progress reporting
        async for event in app.astream(initial_state, {"recursion_limit": 20}):
            for node_name, output in event.items():
                final_state.update(output)
                if node_name in PIPELINE_STEPS_LABELS:
                    completed.append(node_name)
                    _update_progress_live(jobs, job_id, node_name, completed, total)

                if final_state.get("status") == "failed":
                    break

        # After completion, save to cache
        if final_state.get("status") == "completed" and final_state.get("parsed_jd"):
            try:
                from database import save_job_posting, save_salary_observation
                jd = final_state["parsed_jd"]
                company = jd.get("company", "Unknown")
                title = jd.get("job_title", "Unknown Role")
                if company != "Unknown" and title != "Unknown Role":
                    await save_job_posting(
                        job_id=final_state["job_id"],
                        job_url=final_state["job_url"],
                        company=company,
                        job_title=title,
                        parsed_jd=jd,
                        raw_html=final_state["html_content"]
                    )
                    # Salary saving logic simplified for brevity but present
                    if jd.get("salary_mentioned") and final_state.get("salary_intelligence"):
                        await save_salary_observation(final_state["job_url"], company, title, jd.get("location"), jd.get("seniority_level"), jd.get("salary_mentioned"), None, 0.8)
            except Exception as e:
                logger.error(f"Failed to save to cache: {e}")

        return final_state

    except asyncio.TimeoutError:
        logger.error(f"[{job_id}] Pipeline timed out")
        return {**final_state, "status": "failed", "error": "Analysis timed out"}
    except Exception as e:
        logger.error(f"[{job_id}] Pipeline error: {e}", exc_info=True)
        return {**final_state, "status": "failed", "error": str(e)}
