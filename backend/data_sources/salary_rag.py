"""
Salary RAG: semantic retrieval of DOL LCA wage statistics.

Instead of brittle string matching against job titles, we embed the query role
and find the nearest occupation (SOC) in a baked-in embedding index built offline
from real DOL LCA disclosure data (see scripts/build_salary_index.py). The index
is a small, read-only NumPy matrix + JSON that ships in the Docker image under
data/salary_index/ — no ChromaDB, no runtime volume, no ephemeral-reset problem.

Returns the same dict shape as data_sources.dol_h1b.get_salary_data so the salary
agent can consume it interchangeably.
"""
import json
import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_EMB: Optional[np.ndarray] = None      # (N, D) float32, L2-normalized
_ENTRIES: Optional[list] = None        # parallel list of {soc_title, national, states}
_LOAD_ATTEMPTED = False

# Full state name -> USPS code, for parsing a location string into a worksite state.
_STATE_MAP = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
_CODES = set(_STATE_MAP.values())


def _load_index() -> bool:
    """Load the baked-in salary index once. Returns True if available."""
    global _EMB, _ENTRIES, _LOAD_ATTEMPTED
    if _LOAD_ATTEMPTED:
        return _EMB is not None
    _LOAD_ATTEMPTED = True

    from config import settings
    emb_path = os.path.join(settings.SALARY_INDEX_DIR, "soc_embeddings.npy")
    wages_path = os.path.join(settings.SALARY_INDEX_DIR, "soc_wages.json")
    if not (os.path.exists(emb_path) and os.path.exists(wages_path)):
        logger.info("Salary RAG index not present — falling back to legacy H1B/LLM path.")
        return False
    try:
        emb = np.load(emb_path).astype(np.float32)
        # L2-normalize rows so a dot product equals cosine similarity.
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _EMB = emb / norms
        with open(wages_path, "r", encoding="utf-8") as f:
            _ENTRIES = json.load(f)
        logger.info(f"Salary RAG index loaded: {len(_ENTRIES)} occupations.")
        return True
    except Exception as e:
        logger.error(f"Failed to load salary RAG index: {e}", exc_info=True)
        _EMB, _ENTRIES = None, None
        return False


def extract_state(location: str) -> Optional[str]:
    """Best-effort parse of a USPS state code from a free-form location string."""
    if not location:
        return None
    loc = location.lower()
    for name, code in _STATE_MAP.items():
        if name in loc:
            return code
    # Fall back to a bare 2-letter token like "Atlanta, GA"
    import re
    for tok in re.findall(r"\b([A-Z]{2})\b", location):
        if tok in _CODES:
            return tok
    return None


async def query_salary_rag(job_title: str, location: str = "", min_similarity: Optional[float] = None) -> dict:
    """
    Retrieve wage stats for the occupation most semantically similar to job_title,
    scoped to the worksite state when possible (national fallback).

    Returns {min, max, median, count, ...} or {"count": 0} when unavailable / no
    confident match.
    """
    if not _load_index():
        return {"count": 0}

    from config import settings
    from rag.embeddings import get_embedding

    threshold = settings.SALARY_RAG_MIN_SIMILARITY if min_similarity is None else min_similarity

    try:
        q = np.asarray(await get_embedding(job_title), dtype=np.float32)
    except Exception as e:
        logger.warning(f"Salary RAG query embedding failed: {e}")
        return {"count": 0}

    qn = np.linalg.norm(q)
    if qn == 0:
        return {"count": 0}
    q = q / qn

    sims = _EMB @ q                      # cosine similarity to every occupation
    best = int(np.argmax(sims))
    best_sim = float(sims[best])
    if best_sim < threshold:
        logger.info(f"Salary RAG: best match sim={best_sim:.2f} < {threshold} for '{job_title}' — no confident occupation.")
        return {"count": 0}

    entry = _ENTRIES[best]
    soc = entry.get("soc_title", "Occupation")
    state = extract_state(location)

    stats = None
    scope = "national"
    if state and entry.get("states", {}).get(state):
        stats = entry["states"][state]
        scope = state
    if stats is None:
        stats = entry.get("national")
    if not stats:
        return {"count": 0}

    logger.info(
        f"Salary RAG matched '{job_title}' -> '{soc}' (sim={best_sim:.2f}, scope={scope}, "
        f"n={stats.get('count')}): median=${stats.get('median'):,}"
    )
    return {
        "min": int(stats["p25"]),
        "max": int(stats["p75"]),
        "median": int(stats["median"]),
        "count": int(stats["count"]),
        "matched_soc": soc,
        "similarity": round(best_sim, 3),
        "scope": scope,
        "year": stats.get("year"),
        "source": "DOL LCA (RAG)",
    }
