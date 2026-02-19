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


def fetch_wikipedia_summary(company: str) -> Optional[dict]:
    """Fetch company summary from Wikipedia API."""
    try:
        # Search for the company
        search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
        # Normalize company name for Wikipedia
        search_name = company.replace(" Inc.", "").replace(" LLC", "").replace(" Corp.", "").strip()

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
        elif response.status_code == 404:
            # Try with "Inc." suffix
            response2 = requests.get(
                f"{search_url}{requests.utils.quote(company)}",
                headers={"User-Agent": "HireScope/1.0 (educational project)"},
                timeout=10,
            )
            if response2.status_code == 200:
                data = response2.json()
                return {
                    "description": data.get("extract", "")[:500],
                    "wikipedia_url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                }
    except Exception as e:
        logger.warning(f"Wikipedia API failed for '{company}': {e}")
    return None


def fetch_company_intel(company: str, use_mock: bool = False) -> dict:
    """
    Fetch company intelligence from public sources.
    Returns a dict with company metadata, recent news, and culture info.
    """
    if use_mock:
        logger.info(f"Using mock company intel for '{company}'")
        mock = MOCK_COMPANY_INTEL.copy()
        mock["name"] = company
        return mock

    intel = {
        "name": company,
        "description": "",
        "ceo": "N/A",
        "founded": "N/A",
        "headquarters": "N/A",
        "employees": "N/A",
        "revenue": "N/A",
        "industry": "Technology",
        "products": [],
        "recent_news": [],
        "culture_highlights": [],
        "glassdoor_rating": None,
        "source": "Wikipedia API",
    }

    # Fetch from Wikipedia
    wiki_data = fetch_wikipedia_summary(company)
    if wiki_data:
        intel["description"] = wiki_data.get("description", "")
        intel["wikipedia_url"] = wiki_data.get("wikipedia_url", "")
        logger.info(f"Fetched Wikipedia data for '{company}'")
    else:
        intel["description"] = f"{company} is a company in the technology sector."
        logger.info(f"No Wikipedia data found for '{company}', using placeholder")

    try:
        from config import settings
        from utils.llm import llm_generate_json

        if settings.GEMINI_API_KEY != "placeholder":
            prompt = f"""Provide company intelligence for {company} based on your knowledge.
Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{{
  "ceo": "<current CEO full name, or 'N/A' if unknown>",
  "founded": "<founding year, or 'N/A'>",
  "headquarters": "<City, State/Country, or 'N/A'>",
  "employees": "<approximate headcount, e.g. '~9,000' or 'N/A'>",
  "revenue": "<latest annual revenue with year, e.g. '$8.4B (2023)' or 'N/A'>",
  "industry": "<primary industry sector>",
  "business_model": "<1-2 sentences about how they make money>",
  "culture_highlights": ["<3-4 key culture traits based on known reputation>"],
  "recent_news": ["<2-3 real, verifiable recent events about this company>"]
}}
Use 'N/A' for any field you are not confident about. Do NOT invent data."""

            ai_data = llm_generate_json(prompt, max_tokens=700, temperature=0.0)
            intel.update(ai_data)
            logger.info(f"Enhanced company intel for '{company}' with Gemini")

    except Exception as e:
        logger.warning(f"Gemini company enrichment failed: {e}")

    return intel
