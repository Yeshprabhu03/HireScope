"""
LangGraph Orchestrator: defines the job analysis workflow as a state machine.
Nodes run sequentially where dependent, and salary/company/interview can run
after JD parsing.
"""
import asyncio
import logging
from typing import TypedDict, Optional, Any

from langgraph.graph import StateGraph, END

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
    try:
        from utils.job_fetcher import get_job_content

        html, text = get_job_content(state["job_url"], use_mock=state.get("use_mock", False))
        return {"html_content": html, "text_content": text, "status": "fetched"}
    except Exception as e:
        logger.error(f"fetch_html_node failed: {e}", exc_info=True)
        return {"html_content": "", "text_content": "", "status": "fetch_failed", "error": str(e)}


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
        # Return minimal fallback
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
        )
        return {"html_report": html, "status": "completed"}
    except Exception as e:
        logger.error(f"generate_report_node failed: {e}", exc_info=True)
        return {"html_report": f"<html><body><h1>Report generation failed</h1><p>{e}</p></body></html>",
                "status": "failed", "error": str(e)}


# ---------------------------------------------------------------------------
# Build the LangGraph workflow
# ---------------------------------------------------------------------------


def build_workflow() -> Any:
    workflow = StateGraph(JobAnalysisState)

    workflow.add_node("fetch_html", fetch_html_node)
    workflow.add_node("parse_jd", parse_jd_node)
    workflow.add_node("fetch_company", fetch_company_node)
    workflow.add_node("fetch_salary", fetch_salary_node)
    workflow.add_node("fetch_interviews", fetch_interviews_node)
    workflow.add_node("generate_report", generate_report_node)

    # Linear flow: fetch → parse → parallel enrichment → report
    workflow.set_entry_point("fetch_html")
    workflow.add_edge("fetch_html", "parse_jd")
    workflow.add_edge("parse_jd", "fetch_company")
    workflow.add_edge("parse_jd", "fetch_salary")
    workflow.add_edge("parse_jd", "fetch_interviews")
    workflow.add_edge("fetch_company", "generate_report")
    workflow.add_edge("fetch_salary", "generate_report")
    workflow.add_edge("fetch_interviews", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_workflow()
    return _graph


async def run_job_analysis(job_id: str, job_url: str) -> dict:
    """
    Run the full job analysis pipeline.
    Returns the final state dict.
    """
    from config import settings

    initial_state: JobAnalysisState = {
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

    graph = get_graph()

    # LangGraph 0.0.x uses synchronous invoke; wrap in executor for async context
    loop = asyncio.get_event_loop()
    final_state = await loop.run_in_executor(None, graph.invoke, initial_state)

    return final_state
