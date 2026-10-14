"""Run the offline evaluation suite and write auditable JSON/Markdown results."""
import argparse
import asyncio
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from evaluation.metrics import mean_metric, retrieval_metrics

DATASET_PATH = REPO_DIR / "tests" / "data" / "evaluation_cases.v1.json"


class ResultCollector:
    def __init__(self):
        self.tests = {}
        self.deselected = []
        self.external_deselected = 0

    def pytest_deselected(self, items):
        self.deselected.extend(item.nodeid for item in items)
        self.external_deselected += sum(item.get_closest_marker("external") is not None for item in items)

    def pytest_runtest_logreport(self, report):
        if (report.when == "call" and report.outcome in {"passed", "failed", "skipped"}) or (report.when == "setup" and report.outcome in {"failed", "skipped"}):
            self.tests[report.nodeid] = {
                "outcome": report.outcome,
                "duration_seconds": round(report.duration, 6),
                "failure": str(report.longrepr) if report.failed else None,
            }


async def run_retrieval_measurements(dataset: dict) -> dict:
    """Measure the real keyword retriever against temporary synthetic corpus files."""
    from config import settings
    from rag.retriever import retrieve_relevant_experiences

    documents = dataset["retrieval_documents"]
    ids_by_text = {doc["text"]: doc["id"] for doc in documents}
    cases = []
    with TemporaryDirectory(prefix="hirescope-eval-") as corpus_dir:
        corpus_path = Path(corpus_dir) / "fixture.json"
        corpus_path.write_text(json.dumps([
            {"experience": d["text"], "company": d.get("company"), "role": d.get("role"), "industry": d.get("industry")}
            for d in documents
        ]), encoding="utf-8")
        with patch.object(settings, "GLASSDOOR_CACHE_DIR", corpus_dir), patch("rag.vector_store.get_collection", side_effect=RuntimeError("offline evaluation disables Chroma")):
            for judgment in dataset["retrieval_queries"]:
                result = await retrieve_relevant_experiences(
                    query=judgment["query"], company=judgment["company"], role=judgment["role"],
                    role_category="software_engineering", industry=judgment["industry"], limit=5, include_general=True,
                )
                ranked = [ids_by_text[text] for text in (result.get("documents") or [[]])[0] if text in ids_by_text]
                # Match returned general evidence to fixture IDs without depending on result ordering metadata.
                general = [doc["id"] for record in result.get("general_evidence", []) for doc in documents if record.get("text") == doc["text"]]
                cases.append({
                    "id": judgment["id"],
                    "eligible_ids": ranked,
                    "semantic_relevant_ids": judgment["relevant"],
                    "general_ids": general,
                    "metrics": retrieval_metrics(ranked, judgment["eligible"], 5),
                    "company_match_rate": _eligibility_rate(ranked, documents, "company", judgment["company"]),
                    "role_match_rate": _eligibility_rate(ranked, documents, "role", judgment["role"]),
                    "expected_no_evidence": not judgment["eligible"],
                    "no_company_evidence_correct": not judgment["eligible"] and not ranked,
                    "general_scope_correct": set(general) == set(judgment["general"]),
                })
    scored = [c["metrics"] for c in cases if not c["expected_no_evidence"]]
    return {
        "definition": "Keyword retrieval over synthetic corpus records. Semantic recall is not measured because offline runs do not call embedding providers.",
        "queries": len(cases),
        "precision_at_5": mean_metric(scored, "precision_at_k"),
        "recall_at_5": mean_metric(scored, "recall_at_k"),
        "mrr": mean_metric(scored, "mrr"),
        "hit_rate": mean_metric(scored, "hit_rate"),
        "company_match_rate": _aggregate_rate(cases, "company_match_rate"),
        "role_match_rate": _aggregate_rate(cases, "role_match_rate"),
        "no_company_evidence_cases": sum(c["expected_no_evidence"] for c in cases),
        "no_company_evidence_correct": sum(c["no_company_evidence_correct"] for c in cases),
        "general_scope_correct": sum(c["general_scope_correct"] for c in cases),
        "general_scope_denominator": len(cases),
        "per_case": cases,
    }


def _eligibility_rate(ids, docs, field, expected):
    if not ids:
        return {"numerator": 0, "denominator": 0, "value": None}
    by_id = {d["id"]: d for d in docs}
    good = sum(1 for item_id in ids if item_id in by_id and " ".join(str(by_id[item_id].get(field) or "").lower().split()) == " ".join(str(expected or "").lower().split()))
    return {"numerator": good, "denominator": len(ids), "value": good / len(ids)}


def _aggregate_rate(cases, key):
    numerator = sum(case[key]["numerator"] for case in cases)
    denominator = sum(case[key]["denominator"] for case in cases)
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None}


def _parser_fixture_metrics(dataset):
    """Score annotated fixture shape only; these are not model extraction predictions."""
    from agents.jd_parser import ParsedJD
    annotations = dataset["parser_annotations"]
    valid = 0
    failures = []
    present = total = 0
    for case in annotations:
        reference = case["reference"]
        total += 2  # exact identity fields used by the parser contract
        present += sum(bool(reference.get(field)) for field in ("company", "job_title"))
        try:
            ParsedJD.model_validate(reference)
            valid += 1
        except Exception as exc:
            failures.append({"case": case["id"], "error": str(exc)})
    return {
        "scope": "reference-fixture contract only; no live or simulated model accuracy claim",
        "schema_validation": {"numerator": valid, "denominator": len(annotations), "value": valid / len(annotations) if annotations else None, "failures": failures},
        "required_identity_field_completeness": {"numerator": present, "denominator": total, "value": present / total if total else None, "fields": ["company", "job_title"]},
        "skill_precision_recall_f1": {"status": "insufficient evaluation data: offline run has no model predictions to compare with annotations"},
    }


def _revision():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=REPO_DIR, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _working_tree_dirty():
    try:
        return bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_DIR, text=True, stderr=subprocess.DEVNULL).strip())
    except Exception:
        return None


def _format_metric(metric):
    return "insufficient evaluation data" if metric.get("value") is None else f"{metric['value']:.3f} ({metric['numerator']}/{metric['denominator']})"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="evaluation/results/latest.json", help="JSON report path (relative to repository root by default)")
    parser.add_argument("--include-external", action="store_true", help="Run opt-in external provider tests; may use credentials and incur cost")
    parser.add_argument("--baseline", help="Compare test outcomes and retrieval metrics with a previous JSON report")
    parser.add_argument("--thresholds", help="Optional JSON quality thresholds, e.g. {\"retrieval_recall_at_5_min\":0.8}")
    args = parser.parse_args()

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    collector = ResultCollector()
    started = time.perf_counter()
    pytest_args = ["-q", str(REPO_DIR / "tests")]
    if args.include_external:
        pytest_args += ["-m", "external"]
    exit_code = pytest.main(pytest_args, plugins=[collector])
    pytest_runtime = time.perf_counter() - started
    retrieval = asyncio.run(run_retrieval_measurements(dataset))

    outcomes = [test["outcome"] for test in collector.tests.values()]
    passed, failed, skipped = outcomes.count("passed"), outcomes.count("failed"), outcomes.count("skipped")
    failures = [{"test": name, **test} for name, test in collector.tests.items() if test["failure"]]
    report = {
        "report_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {"id": dataset["dataset_id"], "version": dataset["version"], "case_count": len(dataset["cases"])},
        "code_revision": _revision(),
        "working_tree_dirty": _working_tree_dirty(),
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "provider_configuration": "offline deterministic tests; live provider calls excluded"},
        "execution": {"command": "python3 -m evaluation.run_eval", "pytest_exit_code": exit_code, "tests_executed": len(collector.tests), "passed": passed, "failed": failed, "skipped": skipped, "deselected": len(collector.deselected), "external_tests_not_run": 0 if args.include_external else collector.external_deselected, "runtime_seconds": round(pytest_runtime, 3), "external_requests": None if args.include_external else 0, "token_usage": None, "estimated_model_cost": None, "cache_hit_rate": None, "external_tests_included": args.include_external},
        "metric_definitions": {"precision_at_k": "relevant eligible documents in first k divided by k", "recall_at_k": "relevant eligible documents in first k divided by labeled eligible documents", "mrr": "mean reciprocal rank of first relevant eligible result", "hit_rate": "queries with at least one relevant eligible result divided by scored queries", "company_match_rate": "returned company-scoped records with exact normalized company match divided by returned company-scoped records", "role_match_rate": "returned company-scoped records passing role eligibility divided by returned company-scoped records"},
        "metrics": {
            "retrieval": retrieval,
            "parser": _parser_fixture_metrics(dataset),
            "generation": {"schema_validity": "deterministic schema validation tests", "unsupported_claim_rate": "not measured; requires human-reviewed claim/evidence annotations across generated reports", "contradiction_rate": "not measured"},
            "performance": {"suite_runtime_seconds": round(pytest_runtime, 3), "label": "offline test-suite runtime; not production pipeline latency", "p50_pipeline_seconds": None, "p95_pipeline_seconds": None},
        },
        "per_case_failures": failures,
        "known_limitations": ["No model quality, factuality, or production latency is inferred from deterministic fixtures.", "Semantic retrieval recall is not measured without the production embedding model.", "Session IDs are client-held capabilities, not verified user identities.", "Active job state remains process-local and can be lost on restart.", "DNS validation can race the network client's later resolution; enforce deployment egress restrictions."],
    }
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        report["baseline_comparison"] = {
            "baseline_revision": baseline.get("code_revision"),
            "passed_delta": passed - baseline.get("execution", {}).get("passed", 0),
            "failed_delta": failed - baseline.get("execution", {}).get("failed", 0),
            "retrieval_recall_delta": _metric_delta(retrieval["recall_at_5"], baseline.get("metrics", {}).get("retrieval", {}).get("recall_at_5", {})),
        }

    if args.thresholds:
        thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
        checks = []
        if "retrieval_recall_at_5_min" in thresholds:
            measured = retrieval["recall_at_5"]["value"]
            checks.append({"name": "retrieval_recall_at_5_min", "threshold": thresholds["retrieval_recall_at_5_min"], "measured": measured, "passed": measured is not None and measured >= thresholds["retrieval_recall_at_5_min"]})
        if "failed_tests_max" in thresholds:
            checks.append({"name": "failed_tests_max", "threshold": thresholds["failed_tests_max"], "measured": failed, "passed": failed <= thresholds["failed_tests_max"]})
        report["threshold_checks"] = checks

    output = Path(args.output)
    if not output.is_absolute():
        output = REPO_DIR / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = output.with_suffix(".md")
    summary.write_text(
        "# HireScope Offline Evaluation\n\n"
        f"Dataset `{dataset['dataset_id']}` v{dataset['version']} · revision `{report['code_revision'] or 'unavailable'}`\n\n"
        f"Tests: {passed} passed, {failed} failed, {skipped} skipped; {len(collector.tests)} executed, {report['execution']['external_tests_not_run']} external cases deselected in {pytest_runtime:.2f}s.\n\n"
        "## Retrieval metrics\n\n"
        f"- Precision@5: {_format_metric(retrieval['precision_at_5'])}\n"
        f"- Recall@5: {_format_metric(retrieval['recall_at_5'])}\n"
        f"- MRR: {_format_metric(retrieval['mrr'])}\n"
        f"- Hit rate: {_format_metric(retrieval['hit_rate'])}\n"
        f"- Company match: {_format_metric(retrieval['company_match_rate'])}\n"
        f"- Role match: {_format_metric(retrieval['role_match_rate'])}\n"
        f"- General-scope classification: {retrieval['general_scope_correct']}/{retrieval['general_scope_denominator']}\n\n"
        "These results measure deterministic keyword retrieval on synthetic evidence. They do not measure production embedding quality or LLM factuality.\n",
        encoding="utf-8",
    )
    print(summary.read_text(encoding="utf-8"))
    print(f"JSON report: {output}")
    print(f"Markdown summary: {summary}")
    return 1 if exit_code or failed or any(not item["passed"] for item in report.get("threshold_checks", [])) else 0


def _metric_delta(current, baseline):
    a, b = current.get("value"), baseline.get("value")
    return None if a is None or b is None else round(a - b, 6)


if __name__ == "__main__":
    raise SystemExit(main())
