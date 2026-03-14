"""
Job Analysis Orchestrator: runs the analysis pipeline as an Agentic State Machine using LangGraph.
"""
import asyncio
import logging
from typing import TypedDict, Optional, List, Annotated
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
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


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def fetch_html_node(state: HireScopeState) -> dict:
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
                if cached_job.get("parsed_jd"):
                    return {
                        "html_content": cached_job["raw_html"],
                        "text_content": "Cached",
                        "parsed_jd": cached_job["parsed_jd"],
                        "status": "parsed"
                    }
                return {
                    "html_content": cached_job["raw_html"],
                    "text_content": "Cached",
                    "status": "fetched"
                }

    html, text = get_job_content(state["job_url"], use_mock=state.get("use_mock", False))
    return {"html_content": html, "text_content": text, "status": "fetched"}


def parse_jd_node(state: HireScopeState) -> dict:
    """Parse job description."""
    if state.get("parsed_jd") and state.get("status") == "parsed":
        logger.info(f"[{state['job_id']}] Skipping JD parsing (loaded from cache)")
        return {}

    logger.info(f"[{state['job_id']}] Parsing job description")
    try:
        from agents.jd_parser import parse_job_description

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        parsed = parse_job_description(state["html_content"], use_mock=use_mock, provider=provider)
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
        return {
            "parsed_jd": {"job_title": "Unknown", "company": "Unknown", "location": "Unknown"},
            "status": "failed",
            "error": str(e),
        }


def browser_retry_node(state: HireScopeState) -> dict:
    """Auto-Fixing Agent: retry fetching with a real browser."""
    logger.warning(f"[{state['job_id']}] Triggering Auto-Fixing Agent with Browser...")
    import subprocess
    import os
    import sys

    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.normpath(os.path.join(base_dir, "..", "utils", "browser_fetch.py"))

    try:
        # Increased timeout to 45s for complex SPAs
        result = subprocess.run([sys.executable, script_path, state["job_url"]], capture_output=True, text=True, timeout=45)
        if result.returncode == 0 and len(result.stdout.strip()) > 500:
            logger.info(f"[{state['job_id']}] Auto-Fixing successful!")
            return {
                "html_content": result.stdout,
                "browser_retried": True,
                "status": "fetched" # Reset to fetched so parse_jd runs again
            }
        else:
            logger.warning(f"[{state['job_id']}] Auto-Fixing failed")
            return {"browser_retried": True}
    except Exception as fix_err:
        logger.error(f"Auto-Fixing failed: {fix_err}")
        return {"browser_retried": True}


def fetch_company_node(state: HireScopeState) -> dict:
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
            cached_company = get_company_snapshot(cache_key)
            if cached_company and cached_company.get("data"):
                snapshot_date_str = cached_company.get("snapshot_date")
                if snapshot_date_str:
                    snapshot_date = datetime.fromisoformat(snapshot_date_str)
                    if datetime.now() - snapshot_date < timedelta(days=30):
                        return {"company_intelligence": cached_company["data"]}

        use_mock = state.get("use_mock", False)
        provider = state.get("provider", "gemini")
        sub_team = state.get("sub_team")
        team_seed = state.get("extracted_team_context")

        intel = fetch_company_intel(
            company,
            role=job_title,
            parsed_jd=jd,
            sub_team=sub_team,
            team_context=team_seed,
            use_mock=use_mock,
            provider=provider
        )

        if company != "Unknown" and intel and not intel.get("error"):
            save_company_snapshot(cache_key, intel)

        return {"company_intelligence": intel}
    except Exception as e:
        logger.error(f"fetch_company_node failed: {e}", exc_info=True)
        return {"company_intelligence": {"name": company, "error": str(e)}}


def fetch_salary_node(state: HireScopeState) -> dict:
    """Analyze salary data."""
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
            jd_text_snippet=jd.get("jd_text_snippet"),
            use_mock=use_mock,
            provider=provider,
        )
        return {"salary_intelligence": salary}
    except Exception as e:
        logger.error(f"fetch_salary_node failed: {e}", exc_info=True)
        return {"salary_intelligence": {"error": str(e), "estimated_range": "N/A"}}


def fetch_interviews_node(state: HireScopeState) -> dict:
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
        intel = analyze_interviews(
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


def generate_report_node(state: HireScopeState) -> dict:
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

# Define basic retry policy for flaky external calls (3 attempts, exponential backoff)
retry_policy = {
    "stop_after_attempt": 3,
    "wait_exponential": {"multiplier": 2, "min": 4, "max": 10},
}

workflow.add_node("fetch_html", fetch_html_node, retry=retry_policy)
workflow.add_node("parse_jd", parse_jd_node, retry=retry_policy)
workflow.add_node("browser_retry", browser_retry_node, retry=retry_policy)
workflow.add_node("fetch_company", fetch_company_node, retry=retry_policy)
workflow.add_node("fetch_salary", fetch_salary_node, retry=retry_policy)
workflow.add_node("fetch_interviews", fetch_interviews_node, retry=retry_policy)
workflow.add_node("generate_report", generate_report_node, retry=retry_policy)

workflow.set_entry_point("fetch_html")

# Define edges
workflow.add_edge("fetch_html", "parse_jd")

workflow.add_conditional_edges(
    "parse_jd",
    router,
    {
        "browser_retry": "browser_retry",
        "fetch_company": "fetch_company",
        END: END
    }
)

workflow.add_edge("browser_retry", "parse_jd")
workflow.add_edge("fetch_company", "fetch_salary")
workflow.add_edge("fetch_salary", "fetch_interviews")
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


async def run_job_analysis(job_id: str, job_url: str, provider: str = "gemini", jobs: dict = None) -> dict:
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
        "browser_retried": False
    }

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
                    save_job_posting(
                        job_url=final_state["job_url"],
                        company=company,
                        job_title=title,
                        parsed_jd=jd,
                        raw_html=final_state["html_content"]
                    )
                    # Salary saving logic simplified for brevity but present
                    if jd.get("salary_mentioned") and final_state.get("salary_intelligence"):
                        save_salary_observation(final_state["job_url"], company, title, jd.get("location"), jd.get("seniority_level"), jd.get("salary_mentioned"), None, 0.8)
            except Exception as e:
                logger.error(f"Failed to save to cache: {e}")

        return final_state

    except asyncio.TimeoutError:
        logger.error(f"[{job_id}] Pipeline timed out")
        return {**final_state, "status": "failed", "error": "Analysis timed out"}
    except Exception as e:
        logger.error(f"[{job_id}] Pipeline error: {e}", exc_info=True)
        return {**final_state, "status": "failed", "error": str(e)}
