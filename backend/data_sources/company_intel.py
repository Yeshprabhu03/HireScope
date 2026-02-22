"""
Company Intelligence: fetches company data from Wikipedia API and public sources.
"""
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

MOCK_COMPANY_INTEL = {
    "name": "Google LLC",
    "description": "Google LLC is an American multinational technology company focusing on search engine technology, online advertising, cloud computing, computer software, quantum computing, e-commerce, artificial intelligence, and consumer electronics.",
    "ceo": "Sundar Pichai",
    "founded": "1998",
    "headquarters": "Mountain View, California, United States",
    "employees": "180,895 (2023)",
    "revenue": "$307.4 billion (2023)",
    "industry": "Technology",
    "parent_company": "Alphabet Inc.",
    "products": ["Google Search", "Google Ads", "Google Cloud", "YouTube", "Android", "Chrome"],
    "recent_news": [
        "Google DeepMind achieves breakthrough in protein structure prediction",
        "Alphabet reports record revenue in Q4 2024",
        "Google Cloud reaches $36B annual run rate",
    ],
    "culture_highlights": [
        "20% time for personal projects",
        "Strong emphasis on data-driven decisions",
        "Collaborative and open work environment",
        "Focus on moonshot thinking",
    ],
    "glassdoor_rating": 4.3,
    "source": "Wikipedia API (mock)",
}


def resolve_company_name(company_input: str) -> str:
    """Resolve common abbreviations to full company names for accurate Wikipedia lookups."""
    aliases = {
        "JPMC": "JPMorgan Chase",
        "JPM": "JPMorgan Chase",
        "MS": "Morgan Stanley",
        "GS": "Goldman Sachs",
        "BAC": "Bank of America",
        "C": "Citigroup",
        "GOOGL": "Google",
        "MSFT": "Microsoft",
        "AWS": "Amazon Web Services",
        "META": "Meta Platforms",
        "AMZN": "Amazon"
    }
    return aliases.get(company_input.upper().strip(), company_input.strip())

def fetch_wikipedia_summary(company: str) -> Optional[dict]:
    """Fetch company summary from Wikipedia API."""
    # Resolve any known abbreviation first
    resolved_company = resolve_company_name(company)
    
    # Build a list of name variations to try
    suffixes_to_strip = [" Inc.", " LLC", " Corp.", " Corporation", " Holdings", " Group", " Ltd.", " Limited", ", Inc.", ", LLC"]
    
    search_names = []
    # Original name
    search_names.append(resolved_company)
    # Progressively strip suffixes
    name = resolved_company
    for suffix in suffixes_to_strip:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    if name != resolved_company:
        search_names.append(name)
    # Also try stripping all suffixes at once
    clean = resolved_company
    for suffix in suffixes_to_strip:
        clean = clean.replace(suffix, "")
    clean = clean.strip()
    if clean not in search_names:
        search_names.append(clean)

    search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
    
    for search_name in search_names:
        try:
            response = requests.get(
                f"{search_url}{requests.utils.quote(search_name)}",
                headers={"User-Agent": "HireScope/1.0 (educational project)"},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "description": data.get("extract", "")[:500],
                    "wikipedia_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                }
        except Exception as e:
            logger.warning(f"Wikipedia API failed for '{search_name}': {e}")
    
    return None


def _mock_company_intel(company: str) -> dict:
    """Helper to generate mock company intel."""
    mock = MOCK_COMPANY_INTEL.copy()
    mock["name"] = company
    return mock


def fetch_company_intel(company: str, role: str = "", use_mock: bool = False, provider: str = "gemini") -> dict:
    """
    Fetch comprehensive company intelligence from Wikipedia and Gemini.
    """
    if use_mock:
        logger.info(f"Using mock company intel for '{company}'")
        return _mock_company_intel(company)

    intel = {
        "name": company,
        "description": "",
        "ceo": "N/A",
        "founded": "N/A",
        "headquarters": "N/A",
        "employees": "N/A",
        "market_cap": "N/A",
        "industry": "Technology",
        "business_unit_overview": "N/A",
        "linkedin_networking": "N/A",
        "products": [],
        "recent_news": [],
        "culture_highlights": [],
        "glassdoor_rating": None,
        "source": "Wikipedia API",
    }
    
    # 1. Base info via Wikipedia
    try:
        # Using the existing fetch_wikipedia_summary for consistency
        wiki_data = fetch_wikipedia_summary(company)
        if wiki_data:
            intel["description"] = wiki_data.get("description", "")
            intel["wikipedia_url"] = wiki_data.get("wikipedia_url", "")
            intel["source"] = "Wikipedia API"
            logger.info(f"Fetched Wikipedia summary for '{company}'")
        else:
            intel["description"] = f"A prominent company in its sector."
            logger.warning(f"Wikipedia fetch failed for '{company}', using placeholder.")
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed for '{company}': {e}")
        intel["description"] = f"A prominent company in its sector."

    # 2. Extract deep metrics and networking targets with LLM
    try:
        from config import settings
        from utils.llm import llm_generate_json

        if settings.GEMINI_API_KEY != "placeholder":
            prompt = f"""Provide company intelligence and networking strategy for the company "{company}", specifically regarding the role of "{role}".
Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{{
  "ceo": "<current CEO full name, or 'N/A' if unknown>",
  "founded": "<founding year, or 'N/A'>",
  "headquarters": "<City, State/Country, or 'N/A'>",
  "employees": "<approximate headcount, e.g. '~9,000' or 'N/A'>",
  "ticker": "<Stock ticker symbol if public, e.g. 'AAPL', 'MSFT', 'ADBE', or 'N/A' if private/unknown>",
  "industry": "<primary industry sector>",
  "business_model": "<1-2 sentences about how they make money>",
  "business_unit_overview": "<Brief intro about the specific business unit/product group related to the '{role}' position inside {company}>",
  "linkedin_networking": "<1-2 sentences advising the user which specific organizational teams, directors, or managers they should try connecting with on LinkedIn for the '{role}' role>",
  "culture_highlights": ["<3-4 key culture traits based on known reputation>"],
  "recent_news": ["<2-3 real, verifiable recent events about this company>"]
}}
Use 'N/A' for any field you are not confident about. Do NOT invent data."""

            ai_data = llm_generate_json(prompt, provider=provider, max_tokens=900, temperature=0.0)
            
            # Fetch real-time market cap using Yahoo Finance
            ticker = ai_data.get("ticker", "N/A")
            market_cap_str = "Not Listed / Private" if not ticker or ticker.upper() == "N/A" else "N/A"
            if ticker and ticker.upper() != "N/A":
                try:
                    import yfinance as yf
                    stock = yf.Ticker(ticker)
                    mcap = stock.info.get("marketCap")
                    if mcap:
                        if mcap >= 1e12:
                            market_cap_str = f"${mcap / 1e12:.2f}T"
                        elif mcap >= 1e9:
                            market_cap_str = f"${mcap / 1e9:.2f}B"
                        else:
                            market_cap_str = f"${mcap / 1e6:.2f}M"
                        intel["source"] = "Wikipedia, Gemini, Yahoo Finance"
                except Exception as e:
                    logger.warning(f"yfinance failed to fetch market cap for {ticker}: {e}")
            
            ai_data["market_cap"] = market_cap_str
            intel.update(ai_data)
            logger.info(f"Enhanced company intel for '{company}' with Gemini")

    except Exception as e:
        logger.warning(f"Gemini company enrichment failed: {e}")

    return intel
