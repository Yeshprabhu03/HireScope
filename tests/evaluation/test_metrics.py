import pytest

from evaluation.metrics import multilabel_counts, precision_recall_f1, retrieval_metrics
from evaluation.benchmark import summarize


@pytest.mark.evaluation
def test_dataset_covers_required_failure_and_retrieval_scenarios(eval_dataset):
    scenarios = {case["scenario"] for case in eval_dataset["cases"]}
    assert len(scenarios) >= 14
    assert {"correct company and correct role", "correct company but incorrect role", "correct role but incorrect company", "job posting with conflicting information"} <= scenarios
    assert len(eval_dataset["retrieval_documents"]) >= 6
    assert all(case.get("acceptance") for case in eval_dataset["cases"])


@pytest.mark.evaluation
def test_skill_metrics_normalize_only_explicit_equivalents():
    counts = multilabel_counts(["PostgreSQL", "TypeScript", "Python"], ["Postgres", "type script", "Rust"])
    assert counts == {"tp": 2, "fp": 1, "fn": 1}
    assert precision_recall_f1(counts) == {"precision": 2 / 3, "recall": 2 / 3, "f1": 2 / 3, **counts}


@pytest.mark.evaluation
def test_retrieval_metrics_report_numerators_denominators_and_empty_labels():
    measured = retrieval_metrics(["d2", "d1", "d3"], ["d1", "d4"], 3)
    assert measured["precision_at_k"] == {"numerator": 1, "denominator": 3, "value": 1 / 3}
    assert measured["recall_at_k"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert measured["mrr"]["value"] == 0.5
    assert retrieval_metrics([], [], 5)["recall_at_k"]["value"] is None


@pytest.mark.evaluation
def test_benchmark_requires_observed_tokens_and_user_supplied_pricing():
    measurements = {"measurement_mode": "live", "runs": [
        {"end_to_end_seconds": 1, "stage_seconds": {"parse": 0.2}, "input_tokens": 100, "output_tokens": 50, "external_request_count": 2, "cache_hits": 1, "cache_lookups": 2},
        {"end_to_end_seconds": 3, "stage_seconds": {"parse": 0.4}, "input_tokens": 300, "output_tokens": 150, "external_request_count": 1, "cache_hits": 0, "cache_lookups": 1},
    ]}
    observed = summarize(measurements)
    assert observed["end_to_end_seconds"] == {"p50": 1.0, "p95": 3.0}
    assert observed["estimated_cost"] is None
    priced = summarize(measurements, {"pricing_version": "user-fixture-v1", "input_per_million": 1.0, "output_per_million": 2.0})
    assert priced["token_usage"] == {"input": 400, "output": 200}
    assert priced["estimated_cost"] == 0.0008
