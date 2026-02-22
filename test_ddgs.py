import asyncio
import sys
from backend.rag.retriever import retrieve_relevant_experiences

def test_live_search():
    print("Testing DDGS Live Web Search fallback...")
    # This should fail ChromaDB and Keyword, dropping into Live DDGS Search
    results = retrieve_relevant_experiences(
        query="software engineer systems",
        company="SpaceX",
        role="Software Engineer",
        industry="Aerospace",
        limit=2
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    
    print(f"Retrieved {len(docs)} documents.")
    for i, doc in enumerate(docs):
        print(f"\n--- DOC {i} (URL: {metas[i].get('source_url')}) ---")
        print(doc[:200] + "...\n")

if __name__ == "__main__":
    test_live_search()
