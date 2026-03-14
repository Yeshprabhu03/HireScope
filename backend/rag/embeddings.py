"""
Embedding utilities using OpenAI text-embedding-3-small.
"""
import logging
from typing import List
import httpx
from config import settings

logger = logging.getLogger(__name__)

# Singleton client — created once at module load, reused across all embedding calls
_http_client: httpx.AsyncClient = None
_openai_client = None

def _get_openai_client():
    global _http_client, _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI
        _http_client = httpx.AsyncClient()
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, http_client=_http_client)
    return _openai_client


async def get_embedding(text: str, use_mock: bool = False) -> List[float]:
    """Get embedding vector for a text string."""
    if use_mock:
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(((h >> i) & 0xFF) / 255.0 - 0.5) for i in range(384)]

    try:
        client = _get_openai_client()
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text[:8000],
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding failed: {e}", exc_info=True)
        raise


async def get_embeddings_batch(texts: List[str], use_mock: bool = False) -> List[List[float]]:
    """Get embeddings for a batch of texts."""
    if use_mock:
        return [await get_embedding(t, use_mock=True) for t in texts]

    try:
        client = _get_openai_client()
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i : i + 100]
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=[t[:8000] for t in batch],
            )
            all_embeddings.extend([d.embedding for d in response.data])
        return all_embeddings
    except Exception as e:
        logger.error(f"Batch embedding failed: {e}", exc_info=True)
        raise
