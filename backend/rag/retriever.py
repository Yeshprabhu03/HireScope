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
_ROLE_STOP_WORDS = {"senior", "junior", "staff", "lead", "principal", "associate", "director", "manager", "the", "and", "for"}
_ROLE_FAMILY_WORDS = {"engineer", "developer", "analyst", "manager", "specialist", "architect", "designer", "researcher", "scientist"}
_ROLE_CONTRASTS = {"backend": "frontend", "frontend": "backend", "back": "front", "front": "back", "infrastructure": "application", "application": "infrastructure"}


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _tokens(value: str) -> set[str]:
    return {word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")) else word for word in _normalize(value).split()}


def _role_matches(target_role: str, evidence_role: str) -> bool:
    target = set(_normalize(target_role).split()) - _ROLE_STOP_WORDS
    evidence = set(_normalize(evidence_role).split()) - _ROLE_STOP_WORDS
    if any(opposite in evidence for word in target if (opposite := _ROLE_CONTRASTS.get(word))):
        return False
    distinctive_target = target - _ROLE_FAMILY_WORDS
    distinctive_evidence = evidence - _ROLE_FAMILY_WORDS
    if distinctive_target and distinctive_evidence and not distinctive_target.intersection(distinctive_evidence):
        return False
    dice = 2 * len(target & evidence) / (len(target) + len(evidence)) if target and evidence else 0
    return dice >= 0.6


def _keyword_search_corpus(query: str, company: str, role: str, limit: int, *, general: bool = False, industry: str = "", **kwargs) -> dict:
    """
    Fallback: keyword search over the JSON interview corpus files.
    Returns docs in the same shape as ChromaDB results.
    """
    from config import settings
    corpus_dir = settings.GLASSDOOR_CACHE_DIR

    if not os.path.exists(corpus_dir):
        return {"documents": [], "metadatas": [], "distances": []}

    query_words = _tokens(query)
    company_lower = _normalize(company)
    role_words = set(_normalize(role).split()) - _ROLE_STOP_WORDS
    industry_lower = _normalize(industry)

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
            if not isinstance(record, dict):
                continue
            text = record.get("experience", "")
            if not text:
                continue

            text_lower = text.lower()
            meta = {
                "company": str(record.get("company") or "").lower(),
                "role": str(record.get("role") or ""),
                "industry": str(record.get("industry") or ""),
                "evidence_scope": str(record.get("evidence_scope") or record.get("scope") or ""),
                "difficulty": record.get("difficulty", "unknown"),
                "outcome": record.get("outcome", "unknown"),
                "date": record.get("date", ""),
            }

            # Relevance scoring
            score = 0.0
            # Company-specific evidence always requires an explicit company match.
            company_matches = bool(company_lower and company_lower not in {"unknown", "n a"} and _normalize(meta["company"]) == company_lower)
            role_matches = _role_matches(role, meta["role"])
            text_words = _tokens(text)
            query_overlap = query_words & text_words
            industry_matches = bool(industry_lower and (industry_lower in _normalize(text) or industry_lower == _normalize(meta.get("industry"))))
            if general:
                # General patterns require explicit industry evidence. They remain
                # separate from company evidence and never satisfy company claims.
                explicit_general = meta["evidence_scope"] == "industry_general"
                if company_matches or (meta["company"] and not explicit_general) or not industry_matches or not query_overlap:
                    continue
                meta["evidence_scope"] = "industry_general"
                score += 0.25
                if role_matches:
                    score += 0.5
            else:
                if not company_matches or not role_matches:
                    continue
                meta["evidence_scope"] = "company_role"
                score += 1.5
            # Query keyword overlap in experience text
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
    include_general: bool = False,
) -> dict:
    """
    Retrieve relevant interview experience chunks.
    Tries ChromaDB first with strict role_category filtering.
    """
    empty = {"documents": [], "metadatas": [], "distances": []}
    if use_mock:
        return empty

    # Try ChromaDB
    try:
        from rag.vector_store import get_collection
        from rag.embeddings import get_embedding

        collection = get_collection()
        if collection.count() > 0:
            query_embedding = await get_embedding(query)

            # Keep Chroma's candidate pool large enough to find target-role items
            # after local eligibility checks; filter exact scope before returning.
            where = {}
            company_key = _normalize(company)
            if company_key and company_key not in {"unknown", "n a"}:
                where["company"] = company_key
            if role_category:
                where["role_category"] = role_category

            query_kwargs: dict = {
                "query_embeddings": [query_embedding],
                "n_results": min(max(limit * 10, limit), collection.count()),
            }
            if where:
                query_kwargs["where"] = {"$and": [{key: value} for key, value in where.items()]} if len(where) > 1 else where

            results = collection.query(**query_kwargs)

            if results.get("documents") and results["documents"][0]:
                docs = results["documents"][0]
                metas = (results.get("metadatas") or [[]])[0]
                keep = [i for i, meta in enumerate(metas) if meta and company_key and _normalize(meta.get("company")) == company_key and _role_matches(role, meta.get("role"))]
                distances = results.get("distances") or [[]]
                company_results = {
                    "documents": [[docs[i] for i in keep][:limit]],
                    "metadatas": [[dict(metas[i], evidence_scope="company_role") for i in keep][:limit]],
                    "distances": [[distances[0][i] for i in keep if i < len(distances[0])][:limit]] if distances and distances[0] else [],
                }
                if keep:
                    logger.info(f"ChromaDB returned {len(keep)} eligible results for company='{company}', role='{role}'")
                if include_general:
                    general_where = {"role_category": role_category} if role_category else None
                    broad_kwargs = {**query_kwargs, "n_results": min(max(limit * 10, limit), collection.count())}
                    if general_where:
                        broad_kwargs["where"] = general_where
                    else:
                        broad_kwargs.pop("where", None)
                    broad = collection.query(**broad_kwargs)
                    general_docs, general_metas = broad.get("documents", [[]])[0], (broad.get("metadatas") or [[]])[0]
                    query_terms = _tokens(query) - _ROLE_STOP_WORDS
                    gen_keep = [i for i, meta in enumerate(general_metas) if meta and _normalize(meta.get("company")) != company_key and meta.get("evidence_scope") == "industry_general" and industry and (_normalize(industry) in _normalize(general_docs[i]) or _normalize(industry) == _normalize(meta.get("industry"))) and (_role_matches(role, meta.get("role")) or bool(query_terms & _tokens(general_docs[i])))]
                    company_results["general_evidence"] = [{"text": general_docs[i], "metadata": dict(general_metas[i], evidence_scope="industry_general")} for i in gen_keep[:limit]]
                if company_results["documents"][0] or company_results.get("general_evidence"):
                    return company_results
    except Exception as e:
        logger.debug(f"ChromaDB unavailable or query failed: {e}")



    # Keyword-based fallback over JSON corpus
    logger.info(f"Using keyword search fallback for company='{company}', role='{role}'")
    results = _keyword_search_corpus(query, company, role, limit, industry=industry)
    if include_general:
        general_result = _keyword_search_corpus(query, company, role, limit, general=True, industry=industry)
        general_docs = (general_result.get("documents") or [[]])[0]
        general_metas = (general_result.get("metadatas") or [[]])[0]
        results["general_evidence"] = [{"text": doc, "metadata": meta} for doc, meta in zip(general_docs, general_metas)]

    return results
