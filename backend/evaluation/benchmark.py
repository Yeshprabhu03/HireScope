"""Summarize caller-collected stage timings and provider usage without guessed prices."""
import argparse
import json
import math
from pathlib import Path


def percentile(values: list[float], p: float):
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(p * len(ordered)) - 1)
    return ordered[index]


def summarize(measurements: dict, pricing: dict | None = None) -> dict:
    runs = measurements.get("runs", [])
    latencies = [float(run["end_to_end_seconds"]) for run in runs if run.get("end_to_end_seconds") is not None]
    result = {
        "run_count": len(latencies),
        "latency_source": measurements.get("measurement_mode", "unspecified"),
        "end_to_end_seconds": {"p50": percentile(latencies, 0.50), "p95": percentile(latencies, 0.95)},
        "per_stage_seconds": {},
        "external_request_count": sum(run.get("external_request_count", 0) for run in runs) if all("external_request_count" in run for run in runs) else None,
        "cache_hit_rate": _cache_hit_rate(runs),
        "token_usage": None,
        "estimated_cost": None,
    }
    stage_names = {stage for run in runs for stage in run.get("stage_seconds", {})}
    for stage in sorted(stage_names):
        vals = [float(run["stage_seconds"][stage]) for run in runs if stage in run.get("stage_seconds", {})]
        result["per_stage_seconds"][stage] = {"p50": percentile(vals, 0.50), "p95": percentile(vals, 0.95), "samples": len(vals)}
    if runs and all("input_tokens" in run and "output_tokens" in run for run in runs):
        input_tokens = sum(run["input_tokens"] for run in runs)
        output_tokens = sum(run["output_tokens"] for run in runs)
        result["token_usage"] = {"input": input_tokens, "output": output_tokens}
        if pricing and "input_per_million" in pricing and "output_per_million" in pricing:
            result["estimated_cost"] = round(input_tokens * pricing["input_per_million"] / 1_000_000 + output_tokens * pricing["output_per_million"] / 1_000_000, 8)
    return result


def _cache_hit_rate(runs):
    if not runs or not all("cache_hits" in run and "cache_lookups" in run for run in runs):
        return None
    lookups = sum(run["cache_lookups"] for run in runs)
    return sum(run["cache_hits"] for run in runs) / lookups if lookups else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("measurements", help="JSON file with repeated run timings and optionally token counts")
    parser.add_argument("--pricing", help="Optional JSON file with user-supplied input_per_million/output_per_million and pricing_version")
    args = parser.parse_args()
    measurements = json.loads(Path(args.measurements).read_text(encoding="utf-8"))
    pricing = json.loads(Path(args.pricing).read_text(encoding="utf-8")) if args.pricing else None
    print(json.dumps({"measurement_mode": measurements.get("measurement_mode"), "pricing_version": pricing.get("pricing_version") if pricing else None, "summary": summarize(measurements, pricing)}, indent=2))


if __name__ == "__main__":
    main()
