import logging
from typing import Dict, Optional, Any
from utils.llm import llm_generate_json

logger = logging.getLogger(__name__)

async def get_glassdoor_data(company_name: str, provider: str = "gemini") -> Dict[str, Any]:
    """
    Retrieves Glassdoor rating and insights for a company.
    In a production app, this would use a real Glassdoor API or a specialized scraper.
    Here, we use Gemini's knowledge to provide a 'real-ish' baseline and structure.
    """
    logger.info(f"Fetching Glassdoor data for '{company_name}'")

    prompt = f"""Provide current Glassdoor data for the company "{company_name}".
Include the overall rating, approximate review count, and 2-3 common 'Pro' and 'Con' themes from recent reviews.

Return ONLY valid JSON with this structure:
{{
  "rating": <float, e.g. 4.1>,
  "review_count": "<string, e.g. '15k+'>",
  "pros": ["<theme 1>", "<theme 2>"],
  "cons": ["<theme 1>", "<theme 2>"],
  "url": "<URL to the company's Glassdoor page, or 'N/A'>"
}}
If you are unsure about the exact rating, provide your best estimate based on 2024/2025 market knowledge. If the company is unknown, return all fields as 'N/A' or 0."""

    try:
        data = await llm_generate_json(prompt, provider=provider, temperature=0.0)
        return data
    except Exception as e:
        logger.error(f"Failed to fetch Glassdoor data via LLM: {e}")
        return {
            "rating": 0,
            "review_count": "N/A",
            "pros": [],
            "cons": [],
            "url": "N/A"
        }
