from duckduckgo_search import DDGS

print("Testing DDGS...")
try:
    results = DDGS().text("SpaceX software engineer interview site:reddit.com", max_results=3)
    results2 = DDGS().text("SpaceX software engineer interview site:glassdoor.com", max_results=3)
    print("Reddit:", len(results) if results else 0)
    print("Glassdoor:", len(results2) if results2 else 0)
except Exception as e:
    print(f"Error: {e}")
