"""
RAG Retriever: embeds a query and retrieves relevant interview experiences from ChromaDB.
Falls back to keyword-based search over the JSON corpus when ChromaDB is unavailable.
"""
import json
import logging
import os
import re
from typing import Optional, List

logger = logging.getLogger(__name__)


def _keyword_search_corpus(query: str, company: str, role: str, limit: int, **kwargs) -> dict:
    """
    Fallback: keyword search over the JSON interview corpus files.
    Returns docs in the same shape as ChromaDB results.
    """
    from config import settings
    corpus_dir = settings.GLASSDOOR_CACHE_DIR

    if not os.path.exists(corpus_dir):
        return {"documents": [], "metadatas": [], "distances": []}

    query_words = set(query.lower().split())
    company_lower = " ".join(re.findall(r"[a-z0-9]+", company.lower())) if company else ""
    role_words = set(re.findall(r"[a-z0-9]+", role.lower())) if role else set()
    stop_words = {"senior", "junior", "staff", "lead", "principal", "associate", "director", "manager", "the", "and", "for"}
    role_words -= stop_words

    scored: list[tuple[float, str, dict]] = []

    for filename in os.listdir(corpus_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(corpus_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        records = data if isinstance(data, list) else [data]
        for record in records:
            text = record.get("experience", "")
            if not text:
                continue

            text_lower = text.lower()
            meta = {
                "company": str(record.get("company") or "").lower(),
                "role": str(record.get("role") or ""),
                "difficulty": record.get("difficulty", "unknown"),
                "outcome": record.get("outcome", "unknown"),
                "date": record.get("date", ""),
            }

            # Relevance scoring
            score = 0.0
            # Company-specific evidence always requires an explicit company match.
            if not company_lower or company_lower.strip() in {"unknown", "n/a"}:
                continue
            candidate_company = " ".join(re.findall(r"[a-z0-9]+", meta["company"]))
            if company_lower.strip() != candidate_company:
                continue
            score += 1.0
            # Role word overlap
            candidate_role_words = set(re.findall(r"[a-z0-9]+", meta["role"].lower())) - stop_words
            role_overlap = role_words & candidate_role_words
            role_similarity = (2 * len(role_overlap) / (len(role_words) + len(candidate_role_words))) if role_words and candidate_role_words else 0
            if role_similarity < 0.6:
                continue
            score += 0.5 + 0.1 * len(role_overlap)
            # Query keyword overlap in experience text
            text_words = set(text_lower.split())
            query_overlap = query_words & text_words
            score += 0.05 * len(query_overlap)

            if score > 0:
                scored.append((score, text, meta))

    # Sort by score descending, take top results
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    if not top:
        return {"documents": [], "metadatas": [], "distances": []}

    return {
        "documents": [[item[1] for item in top]],
        "metadatas": [[item[2] for item in top]],
        "distances": [[round(1.0 - item[0], 3) for item in top]],
    }


async def retrieve_relevant_experiences(
    query: str,
    company: str = "",
    role: str = "",
    role_category: str = "",
    industry: str = "",
    limit: int = 5,
    use_mock: bool = False,
) -> dict:
    """
    Retrieve relevant interview experience chunks.
    Tries ChromaDB first with strict role_category filtering.
    """
    if use_mock:
        return {"documents": [], "metadatas": [], "distances": []}

    # Try ChromaDB
    try:
        from rag.vector_store import get_collection
        from rag.embeddings import get_embedding

        collection = get_collection()
        if collection.count() > 0:
            query_embedding = await get_embedding(query)

            # Query broadly enough for company spelling variations, then enforce
            # exact normalized company and specific role relevance locally.
            where = {}
            if role_category:
                where["role_category"] = role_category

            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": min(limit, collection.count()),
            }
            if where:
                query_kwargs["where"] = where

            results = collection.query(**query_kwargs)

            if results.get("documents") and results["documents"][0]:
                docs = results["documents"][0]
                metas = (results.get("metadatas") or [[]])[0]
                normalize = lambda value: " ".join("".join(c.lower() if c.isalnum() else " " for c in str(value or "")).split())
                company_key = normalize(company)
                stop_words = {"senior", "junior", "staff", "lead", "principal", "associate", "director", "manager", "the", "and", "for"}
                role_words = set(normalize(role).split()) - stop_words
                keep = []
                for i, meta in enumerate(metas):
                    candidate_words = set(normalize(meta.get("role")).split()) - stop_words
                    overlap = len(role_words & candidate_words)
                    similarity = (2 * overlap / (len(role_words) + len(candidate_words))) if role_words and candidate_words else 0
                    if company_key and normalize(meta.get("company")) == company_key and similarity >= 0.6:
                        keep.append(i)
                if keep:
                    results["documents"][0] = [docs[i] for i in keep][:limit]
                    results["metadatas"][0] = [metas[i] for i in keep][:limit]
                    if results.get("distances"):
                        results["distances"][0] = [results["distances"][0][i] for i in keep][:limit]
                    logger.info(f"ChromaDB returned {len(keep)} verified results for company='{company}', role='{role}'")
                    return results
            else:
                 # If no strict company match, we return empty so the pipeline can trigger the on-demand scraper!
                 logger.info(f"ChromaDB empty for company '{company}', returning empty to trigger on-demand pipeline.")
                 return {"documents": [], "metadatas": [], "distances": []}
    except Exception as e:
        logger.debug(f"ChromaDB unavailable or query failed: {e}")



    # Keyword-based fallback over JSON corpus
    logger.info(f"Using keyword search fallback for company='{company}', role='{role}'")
    results = _keyword_search_corpus(query, company, role, limit, industry=industry)

    return results
