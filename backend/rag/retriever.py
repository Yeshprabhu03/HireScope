"""
RAG Retriever: embeds a query and retrieves relevant interview experiences from ChromaDB.
"""
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


def retrieve_relevant_experiences(
    query: str,
    company: str = "",
    role: str = "",
    limit: int = 5,
    use_mock: bool = False,
) -> dict:
    """
    Embed the query and retrieve relevant interview experience chunks from ChromaDB.
    Returns a dict with 'documents', 'metadatas', and 'distances'.
    """
    if use_mock:
        return {
            "documents": [
                ["We had 4 rounds: phone screen, 2 coding interviews, and system design. "
                 "Coding questions focused on arrays, trees, and dynamic programming. "
                 "System design covered designing a URL shortener."],
                ["Behavioral questions focused on leadership and conflict resolution. "
                 "Tell me about a time you disagreed with your manager and how you resolved it."],
                ["The technical screen was on HackerRank. 2 medium-difficulty problems in 90 minutes. "
                 "One was a graph traversal problem, the other was string manipulation."],
            ],
            "metadatas": [
                [{"company": company or "google", "role": role, "difficulty": "hard", "outcome": "offer"}],
                [{"company": company or "google", "role": role, "difficulty": "medium", "outcome": "offer"}],
                [{"company": company or "google", "role": role, "difficulty": "hard", "outcome": "no offer"}],
            ],
            "distances": [[0.15], [0.22], [0.31]],
        }

    try:
        from rag.vector_store import get_collection
        from rag.embeddings import get_embedding

        collection = get_collection()

        if collection.count() == 0:
            logger.warning("ChromaDB collection is empty. Run indexing first.")
            return {"documents": [], "metadatas": [], "distances": []}

        query_embedding = get_embedding(query)

        # Build where filter
        where = {}
        if company and company.lower() not in ("unknown", "n/a", ""):
            where["company"] = company.lower()

        query_kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": min(limit, collection.count()),
        }
        if where:
            query_kwargs["where"] = where

        results = collection.query(**query_kwargs)
        return results

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}", exc_info=True)
        return {"documents": [], "metadatas": [], "distances": [], "error": str(e)}
