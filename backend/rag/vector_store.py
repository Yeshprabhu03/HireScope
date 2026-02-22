"""
ChromaDB vector store for interview experiences.
Run with --index to populate: python rag/vector_store.py --index
"""
import argparse
import json
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

_chroma_client = None
_collection = None


def get_chroma_client():
    """Get or create ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        from config import settings

        persist_dir = settings.CHROMA_PERSIST_DIR
        os.makedirs(persist_dir, exist_ok=True)

        try:
            # ChromaDB 0.4.x API
            _chroma_client = chromadb.Client(
                ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=persist_dir,
                    anonymized_telemetry=False,
                )
            )
        except Exception:
            # Fallback to newer API style
            _chroma_client = chromadb.PersistentClient(path=persist_dir)

        logger.info(f"ChromaDB initialized at {persist_dir}")
    return _chroma_client


def get_collection():
    """Get or create the interview experiences collection."""
    global _collection
    if _collection is None:
        from config import settings

        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Collection '{settings.CHROMA_COLLECTION_NAME}' ready ({_collection.count()} docs)")
    return _collection


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def index_interview_corpus(corpus_dir: str, use_mock_embeddings: bool = False):
    """
    Read all interview JSON files, chunk them, embed, and store in ChromaDB.
    """
    from config import settings
    from rag.embeddings import get_embeddings_batch

    if not os.path.exists(corpus_dir):
        logger.warning(f"Corpus directory not found: {corpus_dir}")
        return

    collection = get_collection()

    all_docs = []
    all_metadatas = []
    all_ids = []

    doc_count = 0
    for role_category in os.listdir(corpus_dir):
        role_dir = os.path.join(corpus_dir, role_category)
        if not os.path.isdir(role_dir):
            continue
            
        for filename in os.listdir(role_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(role_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                records = data if isinstance(data, list) else [data]
                for record in records:
                    experience_text = record.get("experience", "")
                    if not experience_text:
                        continue

                    chunks = chunk_text(experience_text)
                    for i, chunk in enumerate(chunks):
                        doc_id = f"{role_category}_{filename}_{doc_count}_{i}"
                        all_docs.append(chunk)
                        all_metadatas.append({
                            "company": record.get("company", "unknown").lower(),
                            "role": record.get("role", "unknown"),
                            "role_category": role_category,
                            "difficulty": record.get("difficulty", "unknown"),
                            "outcome": record.get("outcome", "unknown"),
                            "date": record.get("date", ""),
                            "source_file": filename,
                        })
                        all_ids.append(doc_id)
                    doc_count += 1

            except Exception as e:
                logger.warning(f"Failed to process {filepath}: {e}")

    if not all_docs:
        logger.info("No documents to index")
        return

    logger.info(f"Indexing {len(all_docs)} chunks from {doc_count} interview records...")

    # Embed in batches
    use_mock = use_mock_embeddings or (
        not hasattr(settings, "OPENAI_API_KEY") or settings.OPENAI_API_KEY == "placeholder"
    )
    embeddings = get_embeddings_batch(all_docs, use_mock=use_mock)

    # Upsert to ChromaDB
    batch_size = 100
    for i in range(0, len(all_docs), batch_size):
        collection.upsert(
            ids=all_ids[i : i + batch_size],
            documents=all_docs[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            metadatas=all_metadatas[i : i + batch_size],
        )

    logger.info(f"Indexed {len(all_docs)} chunks into ChromaDB")

def index_interviews(interviews: list[str], company: str, role: str, role_category: str, use_mock_embeddings: bool = False):
    """
    On-Demand Indexing: Takes raw text experiences, chunks them, and injects 
    directly into ChromaDB memory without needing a JSON file on disk.
    """
    from config import settings
    from rag.embeddings import get_embeddings_batch
    import uuid

    if not interviews:
        return

    collection = get_collection()
    
    all_docs = []
    all_metadatas = []
    all_ids = []

    doc_count = 0
    for experience_text in interviews:
        if not experience_text.strip():
            continue
            
        chunks = chunk_text(experience_text)
        for i, chunk in enumerate(chunks):
            # Use UUIDs to prevent collisions during dynamic ad-hoc injection
            doc_id = f"dynamic_{uuid.uuid4().hex[:8]}_{doc_count}_{i}"
            all_docs.append(chunk)
            all_metadatas.append({
                "company": company.lower(),
                "role": role,
                "role_category": role_category,
                "difficulty": "unknown",
                "outcome": "unknown",
                "date": "dynamic_scrape",
                "source_file": "on_demand_scraper",
            })
            all_ids.append(doc_id)
        doc_count += 1
        
    if not all_docs:
        return
        
    logger.info(f"Injecting {len(all_docs)} dynamic chunks into ChromaDB...")
    
    use_mock = use_mock_embeddings or (
        not hasattr(settings, "OPENAI_API_KEY") or settings.OPENAI_API_KEY == "placeholder"
    )
    embeddings = get_embeddings_batch(all_docs, use_mock=use_mock)

    # Upsert to ChromaDB
    batch_size = 100
    for i in range(0, len(all_docs), batch_size):
        collection.upsert(
            ids=all_ids[i : i + batch_size],
            documents=all_docs[i : i + batch_size],
            embeddings=embeddings[i : i + batch_size],
            metadatas=all_metadatas[i : i + batch_size],
        )

    logger.info(f"Successfully injected {len(all_docs)} dynamic chunks.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", action="store_true", help="Index the interview corpus")
    parser.add_argument("--mock-embeddings", action="store_true", help="Use mock embeddings")
    args = parser.parse_args()

    if args.index:
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from config import settings

        index_interview_corpus(settings.GLASSDOOR_CACHE_DIR, use_mock_embeddings=args.mock_embeddings)
