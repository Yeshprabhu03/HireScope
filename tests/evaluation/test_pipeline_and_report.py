import asyncio
import json

import pytest


def _fake_llm_response(schema, prompt=""):
    name = getattr(schema, "__name__", "")
    if name == "ParsedJD":
        return {"job_title": "Backend Software Engineer", "company": "Northstar Robotics", "location": "Remote", "required_skills": ["Python", "PostgreSQL"], "salary_mentioned": None, "key_responsibilities": ["Build API services"], "salary_conflict": []}
    if name == "CompanyIntel":
        return {"description": "Synthetic company research fixture.", "ceo": "N/A", "founded": "N/A", "headquarters": "N/A", "ticker": "N/A", "industry": "Robotics", "business_model": "N/A", "target_team_confirmed": "N/A", "business_unit_overview": "N/A", "linkedin_networking": "N/A", "culture_highlights": [], "recent_news": [], "revenue_breakdown": [], "org_chart_mermaid": "graph TD; Northstar[Northstar]"}
    if name == "SalaryMarketEstimate":
        return {"min": 120000, "max": 160000, "median": 140000, "base_range": "$120,000-$160,000", "total_comp_range": "N/A", "notes": "Synthetic estimate fixture."}
    if name == "CompatibilityScore":
        return {"overall_grade": "B", "overall_reasoning": "Fixture score based on supplied inputs.", "dimensions": []}
    if name == "ResumeAITailor":
        return {"ats_keywords_to_add": ["Python"], "suggested_bullet_points": [], "skill_gaps": []}
    if name == "InterviewGuide":
        return {"rounds": [], "technical_questions": ["Likely Topic: Python"], "behavioral_questions": [], "difficulty": "medium", "tips": [], "study_guide": [], "process_overview": "No company-specific evidence was available; this is inferred from the job description.", "identified_sources": [], "source": "JD inference"}
    if "Glassdoor" in prompt or "glassdoor" in prompt:
        return {"rating": 0, "review_count": "N/A", "pros": [], "cons": [], "url": "N/A"}
    return {}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.evaluation
@pytest.mark.parametrize("user_context", [None, "Candidate has Python experience."])
async def test_real_langgraph_pipeline_and_report_with_external_boundaries_stubbed(monkeypatch, tmp_path, user_context):
    from config import settings
    from agents.orchestrator import run_job_analysis
    from agents.jd_parser import ParsedJD
    captured_prompts = []
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "offline-fixture-key")
    monkeypatch.setattr(settings, "GLASSDOOR_CACHE_DIR", str(tmp_path / "empty-corpus"))
    (tmp_path / "empty-corpus").mkdir()

    monkeypatch.setattr("utils.job_fetcher.get_job_content", lambda url, use_mock=False: ("<main>synthetic job posting requires Python and PostgreSQL; no salary disclosed</main>", "Backend Software Engineer requires Python and PostgreSQL"))
    async def deterministic_llm(prompt, **kwargs):
        captured_prompts.append(prompt)
        return _fake_llm_response(kwargs.get("response_schema"), prompt)
    monkeypatch.setattr("utils.llm.llm_generate_json", deterministic_llm)
    monkeypatch.setattr("utils.glassdoor.llm_generate_json", deterministic_llm)
    from agents import compatibility_agent
    monkeypatch.setattr(compatibility_agent, "llm_generate_json", deterministic_llm)
    async def wikipedia(*args, **kwargs): return None
    async def no_cache(*args, **kwargs): return None
    async def no_write(*args, **kwargs): return None
    monkeypatch.setattr("data_sources.company_intel.fetch_wikipedia_summary", wikipedia)
    monkeypatch.setattr("database.get_company_snapshot", no_cache)
    monkeypatch.setattr("database.save_company_snapshot", no_write)
    monkeypatch.setattr("database.get_historical_salary", no_cache)
    monkeypatch.setattr("data_sources.company_intel.fetch_market_cap_finnhub", lambda *args, **kwargs: None)
    monkeypatch.setattr("data_sources.company_intel.resolve_ticker_from_name", lambda *args, **kwargs: None)
    monkeypatch.setattr("data_sources.company_intel.fetch_sec_revenue", lambda *args, **kwargs: None)
    monkeypatch.setattr("data_sources.salary_rag.query_salary_rag", no_cache)
    monkeypatch.setattr("data_sources.dol_h1b.load_h1b_data", lambda *args, **kwargs: None)
    monkeypatch.setattr("data_sources.dol_h1b.get_salary_data", lambda *args, **kwargs: {"count": 0})
    monkeypatch.setattr("database.save_job_posting", no_write)
    monkeypatch.setattr("database.save_salary_observation", no_write)
    monkeypatch.setattr("rag.vector_store.get_collection", lambda: (_ for _ in ()).throw(RuntimeError("offline Chroma boundary")))

    result = await run_job_analysis("offline-e2e", "https://jobs.example.org/backend-role", provider="openai", jobs={}, user_context=user_context)
    assert result["status"] == "completed"
    assert result["parsed_jd"]["required_skills"] == ["Python", "PostgreSQL"]
    assert result["interview_intelligence"]["source_count"] == 0
    assert result["interview_intelligence"]["data_warning"] is True
    if user_context:
        assert user_context in "\n".join(captured_prompts)
    else:
        assert "don't have the user's specific skills" in "\n".join(captured_prompts)
    report = result["html_report"]
    assert "Northstar Robotics" in report and "Backend Software Engineer" in report
    assert "Python" in report and "Estimated Range" in report
    assert "From employer&#39;s posted range" not in report and "AI market estimate" in report
    assert "No company-specific evidence was available" in report
    for section in ("Company Intelligence", "Required Skills", "Resume Tailoring", "Compatibility & Fit Score", "Salary Intelligence", "Interview Intelligence"):
        assert section in report


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fetch_failure_ends_graph_without_parsing_or_success(monkeypatch):
    from config import settings
    from agents.orchestrator import run_job_analysis
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    def inaccessible(*args, **kwargs): raise ValueError("source inaccessible")
    monkeypatch.setattr("utils.job_fetcher.get_job_content", inaccessible)
    result = await run_job_analysis("inaccessible", "https://jobs.example.org/missing", jobs={})
    assert result["status"] == "failed"
    assert result["error"] == "source inaccessible"
    assert not result.get("html_report")
    assert result.get("parsed_jd") is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_malformed_parser_output_fails_intermediate_stage(monkeypatch):
    from config import settings
    from agents.orchestrator import run_job_analysis
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    monkeypatch.setattr("utils.job_fetcher.get_job_content", lambda url, use_mock=False: ("<main>synthetic job</main>", "synthetic job"))
    async def malformed(*args, **kwargs): raise ValueError("invalid structured output")
    monkeypatch.setattr("utils.llm.llm_generate_json", malformed)
    result = await run_job_analysis("malformed-stage", "https://jobs.example.org/role", jobs={})
    assert result["status"] == "failed"
    assert "invalid structured output" in result["error"]
    assert not result.get("html_report")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pdf_upload_ingestion_bypasses_url_fetch(monkeypatch):
    from agents.orchestrator import fetch_html_node
    def forbidden_fetch(*args, **kwargs): raise AssertionError("upload should not fetch pseudo-url")
    monkeypatch.setattr("utils.job_fetcher.get_job_content", forbidden_fetch)
    result = await fetch_html_node({"job_id": "pdf-fixture", "job_url": "upload://sample.pdf", "is_upload": True, "use_mock": False})
    assert result == {"status": "fetched"}


@pytest.mark.asyncio
async def test_pipeline_timeout_is_enforced_and_returns_failed_status(monkeypatch):
    from config import settings
    import agents.orchestrator as orchestrator
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    monkeypatch.setattr(orchestrator, "PIPELINE_TIMEOUT_SECONDS", 0.01)
    class SlowGraph:
        async def astream(self, *args, **kwargs):
            await asyncio.sleep(0.1)
            yield {"fetch_html": {"status": "fetched"}}
    monkeypatch.setattr(orchestrator, "app", SlowGraph())
    result = await orchestrator.run_job_analysis("timeout", "https://jobs.example.org/slow", jobs={})
    assert result["status"] == "failed"
    assert result["error"] == "Analysis timed out"


@pytest.mark.asyncio
async def test_pipeline_cancellation_propagates(monkeypatch):
    from config import settings
    import agents.orchestrator as orchestrator
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    class HangingGraph:
        async def astream(self, *args, **kwargs):
            await asyncio.Event().wait()
            if False: yield {}
    monkeypatch.setattr(orchestrator, "app", HangingGraph())
    task = asyncio.create_task(orchestrator.run_job_analysis("cancel", "https://jobs.example.org/slow", jobs={}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_failed_analysis_does_not_display_completed_progress(monkeypatch):
    import main
    from config import settings
    monkeypatch.setattr(settings, "USE_MOCK_DATA", False)
    main.jobs["failed-progress"] = {"session_id": "session-owner-123456", "status": "created", "progress": {"percent": 40, "completed_steps": ["fetch_html"]}}
    async def failed(*args, **kwargs): return {"status": "failed", "error": "parse broke"}
    monkeypatch.setattr("agents.orchestrator.run_job_analysis", failed)
    try:
        await main.run_analysis("failed-progress", "https://jobs.example.org/role", provider="openai")
        assert main.jobs["failed-progress"]["status"] == "failed"
        assert main.jobs["failed-progress"]["progress"]["percent"] == 40
        assert main.jobs["failed-progress"]["progress"]["current_step"] == "failed"
    finally:
        main.jobs.pop("failed-progress", None)


@pytest.mark.evaluation
def test_report_surfaces_salary_conflict_and_missing_company_research():
    from output.report_gen import generate_html_report
    html = generate_html_report(
        parsed_jd={"company": "Northstar Robotics", "job_title": "Backend Software Engineer", "required_skills": ["Python"], "salary_conflict": ["$140,000-$180,000", "$160,000-$200,000"]},
        company_intel={"name": "Northstar Robotics", "error": "research unavailable"},
        salary_intel={"estimated_range": "$120,000 - $160,000", "min": 120000, "max": 160000, "median": 140000, "confidence_score": 0.4, "data_label": "AI market estimate"},
        interview_intel={"source_count": 0, "data_warning": True, "source": "No verified evidence"},
    )
    assert "conflicting salary ranges" in html
    assert "not a resolved employer-posted range" in html
    assert "research unavailable" in html or "No description available" in html
