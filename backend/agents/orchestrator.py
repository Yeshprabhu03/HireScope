"""
Job Analysis Orchestrator: runs the analysis pipeline as a sequential state machine.
Calls each node function directly (no LangGraph) for reliable sequential execution
and real-time progress tracking.
"""
import asyncio
import logging
from typing import TypedDict, Optional

logger = logging.getLogger(__name__)


class JobAnalysisState(TypedDict):
    job_id: str
    job_url: str
    html_content: str
    text_content: str
    parsed_jd: Optional[dict]
    company_intelligence: Optional[dict]
    salary_intelligence: Optional[dict]
    interview_intelligence: Optional[dict]
    html_report: str
    status: str
    error: str
    use_mock: bool
    provider: str
    model_display_name: str


# ---------------------------------------------------------------------------
# Node functions (each takes state, returns partial state update)
# ---------------------------------------------------------------------------


def fetch_html_node(state: JobAnalysisState) -> dict:
    """Fetch HTML from the job URL, utilizing the local cache if available and fresh."""
    logger.info(f"[{state['job_id']}] Fetching HTML from {state['job_url']}")
    from utils.job_fetcher import get_job_content
    from database import get_job_passing
    from datetime import datetime, timedelta

    # Check cache first
    cached_job = get_job_passing(state["job_url"])
    if cached_job:
        scraped_at_str = cached_job.get("scraped_at")
        if scraped_at_str:
            scraped_at = datetime.fromisoformat(scraped_at_str)
            if datetime.now() - scraped_at < timedelta(days=7):
                logger.info(f"[{state['job_id']}] Found fresh cached job posting from {scraped_at_str}")
                # We can skip the parse_jd node completely if we already have the parsed JSON!
                if cached_job.get("parsed_jd"):
                    return {
                        "html_content": cached_job["raw_html"],
                        "text_content": "Cached", # Not strictly needed if parsed_jd exists
                        "parsed_jd": cached_job["parsed_jd"],
                        "status": "parsed" # Fast-forward the status
                    }
                return {
                    "html_content": cached_job["raw_html"],
                    "text_content": "Cached",
                    "status": "fetched"
                }

    # ValueError (blocked domain, login wall, etc.) propagates up so the job
    # is marked failed with the user-facing message — no silent mock fallback.
    html, text = get_job_content(state["job_url"], use_mock=state.get("use_mock", False))
    return {"html_content": html, "text_content": text, "status": "fetched"}


def parse_jd_node(state: JobAnalysisState) -> dict:
    """Parse job description with Claude. Skips if already parsed via cache."""
    # Fast-forward if we loaded parsed_jd from cache
    if state.get("parsed_jd"):
        logger.info(f"[{state['job_id']}] Skipping JD parsing (loaded from cache)")
        return {}

    logger.info(f"[{state['job_id']}] Parsing job description")
    try:
        from agents.jd_parser import parse_job_description

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        parsed = parse_job_description(state["html_content"], use_mock=use_mock, provider=provider)
        return {"parsed_jd": parsed.model_dump(), "status": "parsed"}
    except Exception as e:
        logger.error(f"parse_jd_node failed: {e}", exc_info=True)
        return {
            "parsed_jd": {"job_title": "Unknown", "company": "Unknown", "location": "Unknown",
                          "required_skills": [], "key_responsibilities": [], "seniority_level": "mid",
                          "remote_policy": "unknown", "employment_type": "full-time"},
            "status": "parsed_with_error",
            "error": str(e),
        }


def fetch_company_node(state: JobAnalysisState) -> dict:
    """Fetch company intelligence, utilizing the local cache if available and fresh."""
    jd = state.get("parsed_jd") or {}
    company = jd.get("company", "Unknown")
    job_title = jd.get("job_title", "Unknown Role")
    logger.info(f"[{state['job_id']}] Fetching company intel for '{company}' regarding '{job_title}'")
    
    try:
        from data_sources.company_intel import fetch_company_intel
        from database import get_company_snapshot, save_company_snapshot
        from datetime import datetime, timedelta

        cache_key = f"{company}::{job_title}"

        # Check cache first
        if company != "Unknown":
            cached_company = get_company_snapshot(cache_key)
            if cached_company and cached_company.get("data"):
                snapshot_date_str = cached_company.get("snapshot_date")
                if snapshot_date_str:
                    snapshot_date = datetime.fromisoformat(snapshot_date_str)
                    if datetime.now() - snapshot_date < timedelta(days=30):
                        logger.info(f"[{state['job_id']}] Found fresh cached company snapshot from {snapshot_date_str}")
                        return {"company_intelligence": cached_company["data"]}

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        intel = fetch_company_intel(company, role=job_title, parsed_jd=jd, use_mock=use_mock, provider=provider)
        
        # Save to cache
        if company != "Unknown" and intel and not intel.get("error"):
            save_company_snapshot(cache_key, intel)
            
        return {"company_intelligence": intel}
    except Exception as e:
        logger.error(f"fetch_company_node failed: {e}", exc_info=True)
        return {"company_intelligence": {"name": company, "error": str(e)}}


def fetch_salary_node(state: JobAnalysisState) -> dict:
    """Analyze salary data from H1B and market sources."""
    jd = state.get("parsed_jd") or {}
    logger.info(f"[{state['job_id']}] Analyzing salary for '{jd.get('job_title')}' at '{jd.get('company')}'")
    try:
        from agents.salary_agent import analyze_salary

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        salary = analyze_salary(
            job_title=jd.get("job_title", "Software Engineer"),
            company=jd.get("company", "Unknown"),
            location=jd.get("location", "Unknown"),
            seniority_level=jd.get("seniority_level", "mid"),
            required_skills=jd.get("required_skills", []),
            salary_mentioned=jd.get("salary_mentioned"),
            use_mock=use_mock,
            provider=provider,
        )
        return {"salary_intelligence": salary}
    except Exception as e:
        logger.error(f"fetch_salary_node failed: {e}", exc_info=True)
        return {"salary_intelligence": {"error": str(e), "estimated_range": "N/A"}}


def fetch_interviews_node(state: JobAnalysisState) -> dict:
    """Fetch interview intelligence via RAG."""
    jd = state.get("parsed_jd") or {}
    company_intel = state.get("company_intelligence") or {}
    company = jd.get("company", "Unknown")
    role = jd.get("job_title", "Software Engineer")
    industry = company_intel.get("industry", "Technology")
    logger.info(f"[{state['job_id']}] Fetching interview intel for '{role}' at '{company}' ({industry})")
    try:
        from agents.interview_agent import analyze_interviews

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        intel = analyze_interviews(
            company=company, 
            role=role, 
            industry=industry, 
            parsed_jd=jd,
            company_intel=company_intel,
            use_mock=use_mock, 
            provider=provider
        )
        return {"interview_intelligence": intel}
    except Exception as e:
        logger.error(f"fetch_interviews_node failed: {e}", exc_info=True)
        return {"interview_intelligence": {"error": str(e), "questions": []}}


def generate_report_node(state: JobAnalysisState) -> dict:
    """Generate the final HTML report."""
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
        return {"html_report": f"<html><body><h1>Report generation failed</h1><p>{e}</p></body></html>",
                "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Pipeline steps definition (for progress tracking)
# ---------------------------------------------------------------------------

PIPELINE_STEPS = [
    ("fetch_html",       "🌐 Fetching job page..."),
    ("parse_jd",         "📋 Parsing job description..."),
    ("fetch_company",    "🏢 Gathering company intelligence..."),
    ("fetch_salary",     "💰 Analyzing salary data..."),
    ("fetch_interviews", "🎯 Researching interview questions..."),
    ("generate_report",  "📊 Generating your report..."),
]

# Map step keys to their node functions
NODE_FUNCTIONS = {
    "fetch_html": fetch_html_node,
    "parse_jd": parse_jd_node,
    "fetch_company": fetch_company_node,
    "fetch_salary": fetch_salary_node,
    "fetch_interviews": fetch_interviews_node,
    "generate_report": generate_report_node,
}


def _update_progress(jobs: dict, job_id: str, step_key: str, step_label: str, completed: list, total: int):
    """Update the progress field on a job in the store."""
    percent = int((len(completed) / total) * 100)
    jobs[job_id]["progress"] = {
        "current_step": step_key,
        "current_step_label": step_label,
        "completed_steps": list(completed),
        "total_steps": total,
        "percent": percent,
    }


def _get_model_display_name(provider: str) -> str:
    """Return a human-readable model name for the report."""
    if provider == "gemini":
        return "Gemini 2.0 Flash"
    elif provider == "anthropic":
        return "Claude 3.5 Sonnet"
    elif provider == "openai":
        return "GPT-4o"
    return "AI Assistant"


PIPELINE_TIMEOUT_SECONDS = 90  # Hard cap; prevents jobs from hanging forever


async def run_job_analysis(job_id: str, job_url: str, provider: str = "gemini", jobs: dict = None) -> dict:
    """
    Run the full job analysis pipeline with progress tracking.
    Calls each node directly (sequential) so we can report progress between steps.
    Raises asyncio.TimeoutError if the pipeline exceeds PIPELINE_TIMEOUT_SECONDS.
    """
    from config import settings

    state: JobAnalysisState = {
        "job_id": job_id,
        "job_url": job_url,
        "html_content": "",
        "text_content": "",
        "parsed_jd": None,
        "company_intelligence": None,
        "salary_intelligence": None,
        "interview_intelligence": None,
        "html_report": "",
        "status": "starting",
        "error": "",
        "use_mock": settings.USE_MOCK_DATA,
        "provider": provider,
        "model_display_name": _get_model_display_name(provider),
    }

    completed_steps: list = []
    total = len(PIPELINE_STEPS)
    loop = asyncio.get_event_loop()

    async def _run_pipeline() -> dict:
        nonlocal state, completed_steps
        for step_key, step_label in PIPELINE_STEPS:
            # Report we're starting this step
            if jobs:
                _update_progress(jobs, job_id, step_key, step_label, completed_steps, total)

            # Run the node function in a thread so we don't block the event loop
            node_fn = NODE_FUNCTIONS[step_key]
            partial_update = await loop.run_in_executor(None, node_fn, state)

            # Merge partial update into state
            state.update(partial_update)

            # Mark step as completed
            completed_steps.append(step_key)
            if jobs:
                _update_progress(jobs, job_id, step_key, step_label, completed_steps, total)

        # After all steps, save to Continuous Learning Cache
        if state.get("status") == "completed" and state.get("parsed_jd") and state.get("html_content") and state.get("job_url"):
            try:
                from database import save_job_posting, save_salary_observation
                jd_dict = state["parsed_jd"]
                company = jd_dict.get("company", "Unknown")
                title = jd_dict.get("job_title", "Unknown Role")
                # Only save if we actually know the company to avoid polluting DB with bad parses
                if company != "Unknown" and title != "Unknown Role":
                    logger.info(f"[{state['job_id']}] Saving parsed job to SQLite continuous learning cache")
                    save_job_posting(
                        job_url=state["job_url"],
                        company=company,
                        job_title=title,
                        parsed_jd=jd_dict,
                        raw_html=state["html_content"]
                    )
                    
                    # Phase 2: Save Salary Observation
                    if state.get("salary_intelligence"):
                        salary_intel = state["salary_intelligence"]
                        # We only want to learn from explicit JD mentions to build an organic dataset
                        if jd_dict.get("salary_mentioned") and not salary_intel.get("error"):
                            # Try to find the H1B median we generated as additional context
                            h1b_median = None
                            for est in salary_intel.get("estimates", []):
                                if est.get("source") == "DOL H1B":
                                    h1b_median = est.get("median")
                            
                            logger.info(f"[{state['job_id']}] Saving salary observation for '{title}' at '{company}'")
                            save_salary_observation(
                                job_url=state["job_url"],
                                company=company,
                                job_title=title,
                                location=jd_dict.get("location", "Unknown"),
                                seniority=jd_dict.get("seniority_level", "Unknown"),
                                jd_salary_mentioned=jd_dict.get("salary_mentioned"),
                                h1b_median=h1b_median,
                                confidence_score=0.8
                            )
                            
            except Exception as e:
                logger.error(f"[{state['job_id']}] Failed to save data to cache: {e}")

        return state

    return await asyncio.wait_for(_run_pipeline(), timeout=PIPELINE_TIMEOUT_SECONDS)
