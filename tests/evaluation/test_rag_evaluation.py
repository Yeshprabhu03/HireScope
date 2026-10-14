import json

import pytest

from rag.retriever import retrieve_relevant_experiences


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_keyword_retrieval_measures_semantic_candidate_then_enforces_scope(monkeypatch, tmp_path, eval_dataset):
    from config import settings

    records = [
        {"experience": doc["text"], "company": doc["company"], "role": doc["role"], "industry": doc["industry"]}
        for doc in eval_dataset["retrieval_documents"]
    ]
    (tmp_path / "fixture.json").write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(settings, "GLASSDOOR_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("rag.vector_store.get_collection", lambda: (_ for _ in ()).throw(RuntimeError("offline Chroma boundary")))
    by_text = {doc["text"]: doc["id"] for doc in eval_dataset["retrieval_documents"]}

    for judgment in eval_dataset["retrieval_queries"]:
        result = await retrieve_relevant_experiences(
            judgment["query"], company=judgment["company"], role=judgment["role"],
            industry=judgment["industry"], role_category="software_engineering", include_general=True,
        )
        eligible = [by_text[text] for text in (result.get("documents") or [[]])[0]]
        general = [by_text[item["text"]] for item in result.get("general_evidence", [])]
        assert set(eligible) == set(judgment["eligible"]), judgment["id"]
        assert set(general) == set(judgment["general"]), judgment["id"]
        assert all(meta.get("evidence_scope") == "company_role" for meta in (result.get("metadatas") or [[]])[0])
        assert all(item["metadata"].get("evidence_scope") == "industry_general" for item in result.get("general_evidence", []))


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_chroma_path_filters_company_role_and_keeps_labeled_general_evidence(monkeypatch):
    from rag.retriever import retrieve_relevant_experiences
    docs = ["valid backend", "wrong product role", "wrong company", "wrong frontend", "missing metadata", "general robotics"]
    metas = [
        {"company": "northstar robotics", "role": "Backend Software Engineer", "role_category": "software_engineering", "industry": "Robotics", "evidence_scope": "company_role"},
        {"company": "northstar robotics", "role": "Product Manager", "role_category": "software_engineering", "industry": "Robotics", "evidence_scope": "company_role"},
        {"company": "cedar labs", "role": "Backend Software Engineer", "role_category": "software_engineering", "industry": "Robotics", "evidence_scope": "company_role"},
        {"company": "northstar robotics", "role": "Frontend Software Engineer", "role_category": "software_engineering", "industry": "Robotics", "evidence_scope": "company_role"},
        {"role_category": "software_engineering"},
        {"company": "", "role": "Software Engineer", "role_category": "software_engineering", "industry": "Robotics", "evidence_scope": "industry_general"},
    ]
    class Collection:
        def count(self): return len(docs)
        def query(self, **kwargs):
            where = kwargs.get("where", {})
            if "$and" in where:
                company = next(condition["company"] for condition in where["$and"] if "company" in condition)
                indexes = [i for i, m in enumerate(metas) if m.get("company") == company and m.get("role_category") == "software_engineering"]
            elif where.get("role_category"):
                indexes = [i for i, m in enumerate(metas) if m.get("role_category") == where["role_category"]]
            else:
                indexes = list(range(len(docs)))
            return {"documents": [[docs[i] for i in indexes]], "metadatas": [[metas[i] for i in indexes]], "distances": [[0.1] * len(indexes)]}
    async def embedding(_query): return [0.0]
    monkeypatch.setattr("rag.vector_store.get_collection", lambda: Collection())
    monkeypatch.setattr("rag.embeddings.get_embedding", embedding)
    result = await retrieve_relevant_experiences("Backend Software Engineer Robotics interview", "Northstar Robotics", "Backend Software Engineer", "software_engineering", "Robotics", include_general=True)
    assert result["documents"] == [["valid backend"]]
    assert result["metadatas"][0][0]["evidence_scope"] == "company_role"
    assert [item["text"] for item in result["general_evidence"]] == ["general robotics"]


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_final_interview_prompt_excludes_wrong_role_wrong_company_and_bad_metadata(monkeypatch, eval_dataset):
    from agents.interview_agent import analyze_interviews
    from rag.retriever import retrieve_relevant_experiences

    docs = {item["id"]: item for item in eval_dataset["retrieval_documents"]}
    candidates = ["d1", "d2", "d3", "d4", "d6"]
    captured = {}

    async def fake_retrieve(*args, **kwargs):
        selected = [docs[item] for item in candidates]
        general = docs["d5"]
        return {"documents": [[item["text"] for item in selected]], "metadatas": [[{k: v for k, v in item.items() if k not in {"id", "text", "industry", "scope"}} for item in selected]], "distances": [[0.1] * len(selected)], "general_evidence": [{"text": general["text"], "metadata": {"evidence_scope": "industry_general", "industry": "Robotics", "sources": ["Synthetic corpus"]}}]}

    async def fake_llm(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["schema"] = kwargs["response_schema"]
        return {"rounds": [], "technical_questions": ["Likely Topic: Python"], "behavioral_questions": ["Likely Topic: collaboration"], "difficulty": "medium", "tips": [], "study_guide": [], "process_overview": "No verified process data.", "identified_sources": ["model-invented-source"], "source": "synthetic"}

    monkeypatch.setattr("rag.retriever.retrieve_relevant_experiences", fake_retrieve)
    monkeypatch.setattr("utils.llm.llm_generate_json", fake_llm)
    output = await analyze_interviews("Backend Software Engineer", "Northstar Robotics", industry="Robotics", parsed_jd={"required_skills": ["Python"]}, provider="openai")

    prompt = captured["prompt"]
    assert docs["d1"]["text"] in prompt
    for wrong_id in ("d2", "d3", "d4", "d6"):
        assert docs[wrong_id]["text"] not in prompt
    assert docs["d5"]["text"] in prompt
    assert "not evidence of this company's interview process" in prompt
    assert output["source_count"] == 1
    assert output["general_source_count"] == 1
    assert output["identified_sources"] == ["General Robotics pattern: Synthetic corpus"]


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_no_evidence_and_missing_metadata_report_zero_company_sources(monkeypatch):
    from agents.interview_agent import analyze_interviews

    captured = {}
    async def no_results(*args, **kwargs):
        return {"documents": [], "metadatas": [], "distances": [], "general_evidence": []}
    async def llm(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"rounds": [], "technical_questions": [], "behavioral_questions": [], "difficulty": "medium", "tips": [], "study_guide": [], "process_overview": "Inferred.", "identified_sources": [], "source": "JD inference"}
    monkeypatch.setattr("rag.retriever.retrieve_relevant_experiences", no_results)
    monkeypatch.setattr("utils.llm.llm_generate_json", llm)
    result = await analyze_interviews("Backend Software Engineer", "Northstar Robotics", parsed_jd={"required_skills": []}, provider="openai")
    assert result["source_count"] == 0
    assert result["data_warning"] is True
    assert "No specific technical data available" in captured["prompt"]
    assert "No general industry evidence available" in captured["prompt"]
