"""
Embedding utilities using OpenAI text-embedding-3-small.
"""
import logging
from typing import List
import httpx
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


def get_embedding(text: str, use_mock: bool = False) -> List[float]:
    """Get embedding vector for a text string."""
    if use_mock:
        # Return a deterministic mock embedding (384-dim zeros with hash-based variation)
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(((h >> i) & 0xFF) / 255.0 - 0.5) for i in range(384)]

    try:
        # Fix for potential 'proxies' TypeError in certain httpx/openai version combinations
        # We explicitly provide a clean client.
        http_client = httpx.Client()
        client = OpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],  # Token limit safety
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        raise


def get_embeddings_batch(texts: List[str], use_mock: bool = False) -> List[List[float]]:
    """Get embeddings for a batch of texts."""
    if use_mock:
        return [get_embedding(t, use_mock=True) for t in texts]

    try:
        # Fix for potential 'proxies' TypeError in certain httpx/openai version combinations
        # We explicitly provide a clean client.
        http_client = httpx.Client()
        client = OpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client)
        # Process in batches of 100
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[t[:8000] for t in batch],
            )
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}", exc_info=True)
        raise
