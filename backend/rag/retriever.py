"""
RAG Retriever: embeds a query and retrieves relevant interview experiences from ChromaDB.
Falls back to keyword-based search over the JSON corpus when ChromaDB is unavailable.
"""
import json
import logging
import os
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
    company_lower = company.lower() if company else ""
    industry_lower = kwargs.get("industry", "").lower()
    role_words = set(role.lower().split()) if role else set()

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
                "company": record.get("company", "").lower(),
                "role": record.get("role", ""),
                "difficulty": record.get("difficulty", "unknown"),
                "outcome": record.get("outcome", "unknown"),
                "date": record.get("date", ""),
            }

            # Relevance scoring
            score = 0.0
            # Company match (strong signal)
            if company_lower and company_lower in meta["company"]:
                score += 0.5
            elif company_lower:
                # Partial company name match
                company_words = set(company_lower.split())
                overlap = company_words & set(meta["company"].split())
                score += 0.2 * len(overlap)
            # Role word overlap
            role_overlap = role_words & set(meta["role"].lower().split())
            score += 0.1 * len(role_overlap)
            # Query keyword overlap in experience text
            text_words = set(text_lower.split())
            query_overlap = query_words & text_words
            score += 0.05 * len(query_overlap)

            # Industry match (fallback signal)
            if industry_lower and industry_lower in text_lower:
                score += 0.1

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

            # Try strict match (Company + Role Category)
            where = {}
            if company and company.lower() not in ("unknown", "n/a", ""):
                where["company"] = company.lower()
            if role_category:
                where["role_category"] = role_category

            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": min(limit, collection.count()),
            }
            if where:
                if len(where) > 1:
                    # ChromaDB syntax for multiple conditions
                    query_kwargs["where"] = {"$and": [{"company": where["company"]}, {"role_category": where["role_category"]}]}
                else:
                    query_kwargs["where"] = where

            results = collection.query(**query_kwargs)

            # We must strictly return only company-matched results to prevent cross-contamination
            # of simulated scraper data across different companies.
            if results.get("documents") and results["documents"][0]:
                logger.info(f"ChromaDB returned {len(results['documents'][0])} results for company='{company}', role_category='{role_category}'")
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

    # If still no results and we have an industry, try a broad industry query
    if (not results.get("documents") or not results["documents"][0]) and industry:
        logger.info(f"Broadening search to industry: {industry}")
        results = _keyword_search_corpus(f"{industry} interview process questions", "", role, limit, industry=industry)

    return results
