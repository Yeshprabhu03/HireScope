from data_sources.company_intel import fetch_wikipedia_summary

def test_wiki():
    print("--- Amazon ---")
    amazon = fetch_wikipedia_summary("Amazon")
    print(amazon)
    print("\n--- Bloomberg ---")
    bloomberg = fetch_wikipedia_summary("Bloomberg")
    print(bloomberg)
    print("\n--- JPMC ---")
    jpmc = fetch_wikipedia_summary("JPMC")
    print(jpmc)

if __name__ == "__main__":
    test_wiki()
