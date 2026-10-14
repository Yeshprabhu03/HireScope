# HireScope evaluation guide

## Run the offline evaluation

From `backend/`, run:

```bash
python3 -m evaluation.run_eval
```

The command runs every default test without live provider calls, runs labeled synthetic retrieval cases through the real keyword fallback, and writes `evaluation/results/latest.json` plus `evaluation/results/latest.md`. From the repository root, the direct test command is `pytest -q`.

The pre-existing company-intelligence and Glassdoor benchmarks call live services. They are marked `external` and excluded from the default suite. To run those provider evaluations intentionally, configure the provider credentials and network, then run `pytest -q -m external`. These can incur provider costs and their source data can change.

## Dataset and reference labels

`tests/data/evaluation_cases.v1.json` is synthetic, versioned `1.0.0`, and contains no candidate personal data. Each scenario has an ID, expected behavior, and concrete acceptance checks. Parser annotations include reference company/title, required skills, salary fields, and conflicting salary ranges. Retrieval judgments separately label semantic relevance, evidence eligibility, and explicitly general industry evidence.

To add a regression, add a case with a stable ID, synthetic input, reference facts, and acceptance assertions. For retrieval cases, label both `relevant` and `eligible`: relevant documents can still be ineligible for company-specific claims because company, role, or provenance does not match. Add a prompt-boundary assertion when the concern is what the model actually receives.

## What the metrics mean

- **Required-field completeness:** present reference fields divided by fields required for that case. Parser tests enforce schema and missing-value behavior. The offline suite does not claim model extraction accuracy because it has no real model predictions.
- **Skill precision, recall, and F1:** true-positive, false-positive, and false-negative skill labels after a small explicit alias map (`Postgres`/`PostgreSQL`, `type script`/`TypeScript`, `js`/`JavaScript`, `k8s`/`Kubernetes`). Other names remain distinct. Metric helpers return raw counts and return unavailable values when a denominator is zero.
- **Precision@k:** eligible relevant results in the first k results divided by k. **Recall@k:** those results divided by labeled eligible results. **MRR:** reciprocal rank of the first eligible relevant result. **Hit rate:** whether any eligible relevant result appeared.
- **Company and role match rates:** exact normalized company match and role-eligibility match among returned company-scoped records. Empty result sets have no rate rather than a fabricated 100%.
- **General-scope classification:** counts cases where separately labeled general evidence remains outside company-specific evidence. General patterns require an explicit industry marker; a different company's interview is not automatically generalized.
- **Schema validity:** tests check the real Pydantic parser schema and the shared JSON validation path. They do not claim that all generated factual claims are supported.
- **Unsupported-claim and contradiction rates:** not measured comprehensively. The suite has specific unsupported-claim regression fixtures, but no broad human-reviewed claim/evidence annotation set exists yet.

The retrieval report measures deterministic keyword fallback behavior on synthetic documents. It does not measure production embedding recall or ranking. A percentage is omitted when its labeled denominator is empty. No single overall “AI accuracy” score is produced.

## Wrong-company / wrong-role regression walkthrough

For query `q1`, the synthetic corpus includes a Northstar Robotics backend engineer record (`d1`), a Northstar product manager record (`d2`), a Cedar Labs backend engineer record (`d3`), a Northstar frontend engineer record (`d4`), an explicitly marked general Robotics pattern (`d5`), and a record with no identifying metadata (`d6`). The expected company-role evidence is only `d1`; `d5` may appear in a separate general-pattern prompt section; `d2`, `d3`, `d4`, and `d6` must not appear in that section or be counted as company evidence. The regression test inspects the final prompt passed to the model stub and the source counts, not only a filter helper.

## Compare changes and set thresholds

Save a report before a prompt or retrieval change, then compare a later run:

```bash
python3 -m evaluation.run_eval --baseline evaluation/results/before.json
```

Thresholds are opt-in and supplied by the team rather than chosen to make the fixture pass:

```json
{"retrieval_recall_at_5_min": 0.8, "failed_tests_max": 0}
```

```bash
python3 -m evaluation.run_eval --thresholds evaluation/thresholds.json
```

Baseline comparison currently reports test-count deltas and eligible Recall@5 delta. The default report does not assert thresholds.

## Optional performance and cost measurements

`python3 -m evaluation.benchmark measurements.json` summarizes repeated caller-collected end-to-end and per-stage timings using nearest-rank P50/P95, plus request and cache counts only when all runs supply those measurements. Token usage is emitted only when runs contain observed input/output counts. A cost estimate requires a separate, user-supplied JSON price file with `pricing_version`, `input_per_million`, and `output_per_million`; the tool supplies no price assumptions.

Label `measurement_mode` as `offline_mock` or `live`. Mock timing is not production latency. The built-in report's runtime is the local deterministic test-suite runtime, not pipeline latency. HireScope does not yet expose consistent per-stage request, provider-token, or cache-hit instrumentation in production, so the standard report marks those values unavailable.

## Measured coverage and known gaps

The offline tests cover parser schema handling and missing/conflicting fields; retriever evidence eligibility and the actual interview prompt boundary; provider JSON contracts, malformed responses, timeout and retryable status behavior; a real LangGraph run with external boundaries replaced; report assembly; failed fetch and pipeline timeout behavior; cancellation propagation; progress state; URL scheme/IP/redirect/browser request checks; API key logging; and client-session capability scoping.

The API key remains shared, and a browser session ID is a client-held capability rather than a verified user identity. Active task state is process-local and restart recovery is not tested. DNS resolution validation can race the HTTP client's subsequent lookup; deploy with network-level egress restrictions. Existing external company/Glassdoor evaluations are opt-in and were not run by the offline command. This framework does not establish comprehensive hallucination rates, production latency, monetary cost, or multi-instance job durability.
