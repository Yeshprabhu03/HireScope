"""Small, auditable metrics used by offline evaluation runs."""
from collections.abc import Iterable


SKILL_ALIASES = {
    "postgres": "postgresql",
    "type script": "typescript",
    "js": "javascript",
    "k8s": "kubernetes",
}


def normalize_skill(value: str) -> str:
    normalized = " ".join(str(value).lower().replace("+", " plus ").split())
    return SKILL_ALIASES.get(normalized, normalized)


def multilabel_counts(expected: Iterable[str], actual: Iterable[str]) -> dict:
    expected_set = {normalize_skill(item) for item in expected}
    actual_set = {normalize_skill(item) for item in actual}
    tp = len(expected_set & actual_set)
    fp = len(actual_set - expected_set)
    fn = len(expected_set - actual_set)
    return {"tp": tp, "fp": fp, "fn": fn}


def precision_recall_f1(counts: dict) -> dict:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"precision": precision, "recall": recall, "f1": f1, **counts}


def retrieval_metrics(ranked_ids: list[str], relevant_ids: Iterable[str], k: int) -> dict:
    relevant = set(relevant_ids)
    top = ranked_ids[:k]
    hits = [doc_id for doc_id in top if doc_id in relevant]
    first_rank = next((rank for rank, doc_id in enumerate(top, 1) if doc_id in relevant), None)
    return {
        "precision_at_k": {"numerator": len(hits), "denominator": k, "value": len(hits) / k if k else None},
        "recall_at_k": {"numerator": len(hits), "denominator": len(relevant), "value": len(hits) / len(relevant) if relevant else None},
        "mrr": {"numerator": 1 / first_rank if first_rank else 0.0, "denominator": 1 if relevant else 0, "value": 1 / first_rank if first_rank else (0.0 if relevant else None)},
        "hit_rate": {"numerator": int(bool(hits)), "denominator": 1, "value": float(bool(hits))},
    }


def mean_metric(results: list[dict], name: str) -> dict:
    available = [case[name]["value"] for case in results if case[name]["value"] is not None]
    numerator = sum(case[name]["numerator"] for case in results if case[name]["value"] is not None)
    denominator = sum(case[name]["denominator"] for case in results if case[name]["value"] is not None)
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None, "cases_scored": len(available)}
