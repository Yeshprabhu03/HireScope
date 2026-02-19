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


# ---------------------------------------------------------------------------
# Node functions (each takes state, returns partial state update)
# ---------------------------------------------------------------------------


def fetch_html_node(state: JobAnalysisState) -> dict:
    """Fetch HTML from the job URL."""
    logger.info(f"[{state['job_id']}] Fetching HTML from {state['job_url']}")
    from utils.job_fetcher import get_job_content

    # ValueError (blocked domain, login wall, etc.) propagates up so the job
    # is marked failed with the user-facing message — no silent mock fallback.
    html, text = get_job_content(state["job_url"], use_mock=state.get("use_mock", False))
    return {"html_content": html, "text_content": text, "status": "fetched"}


def parse_jd_node(state: JobAnalysisState) -> dict:
    """Parse job description with Claude."""
    logger.info(f"[{state['job_id']}] Parsing job description")
    try:
        from agents.jd_parser import parse_job_description

        use_mock = state.get("use_mock", False)
        parsed = parse_job_description(state["html_content"], use_mock=use_mock)
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
    """Fetch company intelligence."""
    company = (state.get("parsed_jd") or {}).get("company", "Unknown")
    logger.info(f"[{state['job_id']}] Fetching company intel for '{company}'")
    try:
        from data_sources.company_intel import fetch_company_intel

        use_mock = state.get("use_mock", False)
        intel = fetch_company_intel(company, use_mock=use_mock)
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
        salary = analyze_salary(
            job_title=jd.get("job_title", "Software Engineer"),
            company=jd.get("company", "Unknown"),
            location=jd.get("location", "Unknown"),
            seniority_level=jd.get("seniority_level", "mid"),
            required_skills=jd.get("required_skills", []),
            salary_mentioned=jd.get("salary_mentioned"),
            use_mock=use_mock,
        )
        return {"salary_intelligence": salary}
    except Exception as e:
        logger.error(f"fetch_salary_node failed: {e}", exc_info=True)
        return {"salary_intelligence": {"error": str(e), "estimated_range": "N/A"}}


def fetch_interviews_node(state: JobAnalysisState) -> dict:
    """Fetch interview intelligence via RAG."""
    jd = state.get("parsed_jd") or {}
    company = jd.get("company", "Unknown")
    role = jd.get("job_title", "Software Engineer")
    logger.info(f"[{state['job_id']}] Fetching interview intel for '{role}' at '{company}'")
    try:
        from agents.interview_agent import analyze_interviews

        use_mock = state.get("use_mock", False)
        intel = analyze_interviews(company=company, role=role, use_mock=use_mock)
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


PIPELINE_TIMEOUT_SECONDS = 90  # Hard cap; prevents jobs from hanging forever


async def run_job_analysis(job_id: str, job_url: str, jobs: dict = None) -> dict:
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

        return state

    return await asyncio.wait_for(_run_pipeline(), timeout=PIPELINE_TIMEOUT_SECONDS)
