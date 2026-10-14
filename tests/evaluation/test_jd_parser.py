import pytest
from pydantic import ValidationError

from agents.jd_parser import ParsedJD, parse_job_description
from evaluation.metrics import multilabel_counts, precision_recall_f1


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_real_parser_path_validates_deterministic_annotated_result(monkeypatch, eval_dataset):
    annotation = eval_dataset["parser_annotations"][0]
    output = {**annotation["reference"], "location": "Unknown", "remote_policy": "unknown"}

    async def deterministic_llm(*args, **kwargs):
        assert kwargs["response_schema"] is ParsedJD
        return output

    monkeypatch.setattr("utils.llm.llm_generate_json", deterministic_llm)
    parsed = await parse_job_description(f"<main>{annotation['raw_text']}</main>", provider="openai")
    actual = parsed.model_dump()
    assert actual["company"] == annotation["reference"]["company"]
    assert actual["job_title"] == annotation["reference"]["job_title"]
    counts = multilabel_counts(annotation["reference"]["required_skills"], actual["required_skills"])
    metrics = precision_recall_f1(counts)
    assert metrics["tp"] == 2 and metrics["fp"] == 0 and metrics["fn"] == 0
    assert actual["salary_mentioned"] == annotation["reference"]["salary_mentioned"]


@pytest.mark.asyncio
@pytest.mark.evaluation
async def test_conflicting_salary_annotation_survives_parser_path(monkeypatch, eval_dataset):
    case = next(item for item in eval_dataset["parser_annotations"] if item["id"] == "jd-3")
    async def deterministic_llm(*args, **kwargs):
        return {**case["reference"], "location": "Remote"}
    monkeypatch.setattr("utils.llm.llm_generate_json", deterministic_llm)
    parsed = await parse_job_description(f"<main>{case['raw_text']}</main>", provider="openai")
    assert parsed.salary_mentioned is None
    assert parsed.salary_conflict == case["reference"]["salary_conflict"]


@pytest.mark.evaluation
def test_parsed_jd_rejects_additional_fields_and_wrong_types():
    with pytest.raises(ValidationError):
        ParsedJD.model_validate({"company": "Northstar", "job_title": "Backend Engineer", "required_skills": "Python", "invented_field": True})
    with pytest.raises(ValidationError):
        ParsedJD.model_validate({"required_skills": [42]})


@pytest.mark.evaluation
def test_missing_requirements_remain_empty_not_invented(eval_dataset):
    case = next(item for item in eval_dataset["parser_annotations"] if item["id"] == "jd-2")
    parsed = ParsedJD.model_validate(case["reference"])
    assert parsed.required_skills == []
    assert parsed.salary_mentioned is None
