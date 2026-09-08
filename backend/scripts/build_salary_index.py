"""
Build the salary RAG index from real DOL LCA disclosure data.

WHERE TO GET THE DATA (free):
  https://www.dol.gov/agencies/eta/foreign-labor/performance
  Download "LCA Programs (H-1B, H-1B1, E-3)" disclosure data — the latest
  fiscal year, e.g. "LCA_Disclosure_Data_FY2024.xlsx" (a few hundred MB).

WHAT THIS DOES:
  - Reads the DOL file (.xlsx or .csv)
  - Keeps CERTIFIED cases, annualizes wages by WAGE_UNIT_OF_PAY
  - Aggregates p25/median/p75 wage by (SOC occupation x worksite state) and
    nationally, dropping thin groups (< --min-count)
  - Embeds each distinct occupation title with text-embedding-3-small
  - Writes a small, read-only index to data/salary_index/:
        soc_embeddings.npy   (N x 1536 float32)
        soc_wages.json       (parallel occupation -> national/state wage stats)
  These ship in the Docker image (under data/) and are consumed by
  data_sources/salary_rag.py at runtime. Re-run yearly to refresh.

USAGE:
  export OPENAI_API_KEY=<your-openai-key>
  cd backend
  python scripts/build_salary_index.py --input /path/to/LCA_Disclosure_Data_FY2024.xlsx
  # optional: --min-count 5   --out ../data/salary_index
"""
import argparse
import asyncio
import json
import logging
import os
import sys

import numpy as np
import pandas as pd

# Make backend/ importable when run as `python scripts/build_salary_index.py`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("build_salary_index")

# Column-name candidates (DOL renames columns across fiscal years).
COLS = {
    "soc":   ["SOC_TITLE", "SOC_NAME", "OCCUPATION_TITLE"],
    "state": ["WORKSITE_STATE", "WORKSITE_STATE_1", "WORK_STATE", "STATE_1", "EMPLOYER_STATE"],
    "from":  ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_FROM_1", "PREVAILING_WAGE", "WAGE_RATE_OF_PAY"],
    "to":    ["WAGE_RATE_OF_PAY_TO", "WAGE_RATE_OF_PAY_TO_1"],
    "unit":  ["WAGE_UNIT_OF_PAY", "WAGE_UNIT_OF_PAY_1", "PW_UNIT_OF_PAY"],
    "status": ["CASE_STATUS"],
    "year":  ["RECEIVED_YEAR", "FISCAL_YEAR", "YEAR"],
}

UNIT_MULTIPLIER = {
    "year": 1, "yr": 1, "annual": 1,
    "hour": 2080, "hr": 2080, "hourly": 2080,
    "week": 52, "weekly": 52,
    "bi-weekly": 26, "biweekly": 26, "2 weeks": 26,
    "month": 12, "monthly": 12,
}


def _pick(df: pd.DataFrame, names: list) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None


def _annualize(row_wage, unit) -> float | None:
    if pd.isna(row_wage):
        return None
    mult = UNIT_MULTIPLIER.get(str(unit).strip().lower(), None)
    if mult is None:
        # Heuristic fallback when the unit column is missing/odd.
        if row_wage < 500:
            mult = 2080
        elif row_wage < 10000:
            mult = 52
        else:
            mult = 1
    return float(row_wage) * mult


def load_and_aggregate(path: str, min_count: int) -> dict:
    logger.info(f"Reading {path} ...")
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path, low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    logger.info(f"Loaded {len(df):,} rows, {len(df.columns)} columns.")

    c_soc = _pick(df, COLS["soc"]);   c_state = _pick(df, COLS["state"])
    c_from = _pick(df, COLS["from"]); c_unit = _pick(df, COLS["unit"])
    c_status = _pick(df, COLS["status"]); c_year = _pick(df, COLS["year"])
    if not (c_soc and c_state and c_from):
        raise SystemExit(f"Missing required columns. Found SOC={c_soc}, STATE={c_state}, FROM={c_from}")

    if c_status:
        df = df[df[c_status].astype(str).str.upper().str.startswith("CERTIFIED")]
        logger.info(f"{len(df):,} rows after keeping CERTIFIED cases.")

    wage = pd.to_numeric(df[c_from].astype(str).str.replace(r"[,$]", "", regex=True), errors="coerce")
    unit = df[c_unit] if c_unit else pd.Series([None] * len(df), index=df.index)
    df = df.assign(
        _wage=[_annualize(w, u) for w, u in zip(wage, unit)],
        _soc=df[c_soc].astype(str).str.strip(),
        _state=df[c_state].astype(str).str.strip().str.upper(),
    )
    df = df[(df["_wage"] >= 20000) & (df["_wage"] <= 1500000)]   # sanity
    df = df[df["_soc"].str.len() > 1]
    year = None
    if c_year:
        try:
            year = int(pd.to_numeric(df[c_year], errors="coerce").dropna().mode().iloc[0])
        except Exception:
            year = None

    def _stats(s: pd.Series) -> dict:
        return {
            "p25": int(s.quantile(0.25)), "median": int(s.median()),
            "p75": int(s.quantile(0.75)), "count": int(s.count()), "year": year,
        }

    entries: dict[str, dict] = {}
    # National aggregate per occupation
    for soc, grp in df.groupby("_soc"):
        if len(grp) < min_count:
            continue
        entries[soc] = {"soc_title": soc, "national": _stats(grp["_wage"]), "states": {}}
    # Per-state aggregate per occupation
    for (soc, st), grp in df.groupby(["_soc", "_state"]):
        if soc not in entries or len(grp) < min_count or len(st) != 2:
            continue
        entries[soc]["states"][st] = _stats(grp["_wage"])

    logger.info(f"Aggregated {len(entries):,} occupations (min_count={min_count}, year={year}).")
    return entries


async def embed_titles(titles: list[str]) -> np.ndarray:
    from rag.embeddings import get_embeddings_batch
    logger.info(f"Embedding {len(titles):,} occupation titles ...")
    vecs = await get_embeddings_batch(titles, use_mock=False)
    return np.asarray(vecs, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser(description="Build the salary RAG index from DOL LCA data.")
    ap.add_argument("--input", required=True, help="Path to DOL LCA .xlsx or .csv")
    ap.add_argument("--out", default=None, help="Output dir (default: settings.SALARY_INDEX_DIR)")
    ap.add_argument("--min-count", type=int, default=5, help="Drop occupation/state groups thinner than this")
    args = ap.parse_args()

    from config import settings
    out_dir = args.out or settings.SALARY_INDEX_DIR
    if settings.OPENAI_API_KEY == "placeholder":  # pragma: allowlist secret
        raise SystemExit("OpenAI key is not set — needed to embed occupation titles.")

    entries = load_and_aggregate(args.input, args.min_count)
    if not entries:
        raise SystemExit("No occupations survived aggregation — check the input file / --min-count.")

    ordered = list(entries.values())
    titles = [e["soc_title"] for e in ordered]
    emb = asyncio.run(embed_titles(titles))

    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "soc_embeddings.npy"), emb)
    with open(os.path.join(out_dir, "soc_wages.json"), "w", encoding="utf-8") as f:
        json.dump(ordered, f)

    sample = ordered[0]
    logger.info(f"Wrote index to {out_dir}/ — {len(ordered):,} occupations, embedding dim {emb.shape[1]}.")
    logger.info(f"Example: '{sample['soc_title']}' national median=${sample['national']['median']:,} "
                f"across {len(sample['states'])} states.")
    logger.info("Commit data/salary_index/ so it ships in the Docker image.")


if __name__ == "__main__":
    main()
