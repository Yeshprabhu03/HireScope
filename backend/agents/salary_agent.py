"""
Salary Agent: triangulates salary estimates from 3 sources:
1. DOL H1B disclosure data
2. JD-mentioned salary
3. Claude market-rate reasoning
"""
import json
import logging
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

MOCK_SALARY_INTELLIGENCE = {
    "estimated_range": "$180,000 - $250,000",
    "min": 180000,
    "max": 250000,
    "median": 210000,
    "confidence_score": 0.85,
    "sources_used": ["DOL H1B Data", "JD Mention", "Market Estimate"],
    "breakdown": {
        "base_salary": "$180,000 - $220,000",
        "bonus": "10-20% of base",
        "equity": "$50,000 - $100,000/year (RSU)",
        "total_comp": "$220,000 - $350,000",
    },
    "notes": "Salary range based on H1B disclosure data and market rates for senior engineers at top tech companies.",
}


def parse_salary_from_text(salary_text: Optional[str]) -> Optional[dict]:
    """Extract numeric salary range from free text."""
    if not salary_text:
        return None
    # Match patterns like $180,000 - $250,000 or 180k-250k
    pattern = r"\$?([\d,]+)k?\s*[-–to]+\s*\$?([\d,]+)k?"
    match = re.search(pattern, salary_text, re.IGNORECASE)
    if match:
        low = float(match.group(1).replace(",", ""))
        high = float(match.group(2).replace(",", ""))
        if "k" in salary_text.lower():
            low *= 1000
            high *= 1000
        return {"min": int(low), "max": int(high)}
    return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
def estimate_market_salary_with_claude(
    job_title: str,
    company: str,
    location: str,
    seniority: str,
    skills: list[str],
    use_mock: bool = False,
) -> dict:
    """Use Claude to reason about market compensation rates."""
    if use_mock:
        return {
            "min": 160000,
            "max": 240000,
            "median": 200000,
            "notes": "Market estimate (mock)",
        }

    try:
        from anthropic import Anthropic
        from config import settings

        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = f"""You are a compensation expert. Estimate the salary range for this position.

Job Title: {job_title}
Company: {company}
Location: {location}
Seniority: {seniority}
Key Skills: {", ".join(skills[:10])}

Return ONLY valid JSON with this structure:
{{
  "min": <integer annual salary USD>,
  "max": <integer annual salary USD>,
  "median": <integer annual salary USD>,
  "base_range": "<string like '$X - $Y'>",
  "total_comp_range": "<string including equity/bonus>",
  "notes": "<brief 1-2 sentence explanation>"
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    except Exception as e:
        logger.error(f"Claude salary estimation failed: {e}", exc_info=True)
        return {"min": 120000, "max": 200000, "median": 160000, "notes": "Estimate unavailable"}


def analyze_salary(
    job_title: str,
    company: str,
    location: str,
    seniority_level: str,
    required_skills: list[str],
    salary_mentioned: Optional[str],
    use_mock: bool = False,
) -> dict:
    """
    Triangulate salary from 3 sources and return unified intelligence.
    """
    if use_mock:
        return MOCK_SALARY_INTELLIGENCE

    sources_used = []
    salary_estimates = []

    # Source 1: DOL H1B data
    try:
        from config import settings
        from data_sources.dol_h1b import load_h1b_data, get_salary_data

        df = load_h1b_data(settings.DOL_H1B_DATA_PATH)
        h1b_data = get_salary_data(df, job_title, company, location)
        if h1b_data.get("count", 0) > 0:
            salary_estimates.append(
                {"source": "DOL H1B", "min": h1b_data["min"], "max": h1b_data["max"], "median": h1b_data["median"]}
            )
            sources_used.append("DOL H1B Data")
    except Exception as e:
        logger.warning(f"H1B data lookup failed: {e}")

    # Source 2: JD-mentioned salary
    jd_salary = parse_salary_from_text(salary_mentioned)
    if jd_salary:
        salary_estimates.append(
            {"source": "JD Mention", "min": jd_salary["min"], "max": jd_salary["max"],
             "median": (jd_salary["min"] + jd_salary["max"]) // 2}
        )
        sources_used.append("JD Mention")

    # Source 3: Claude market estimate
    market = estimate_market_salary_with_claude(
        job_title, company, location, seniority_level, required_skills, use_mock=use_mock
    )
    salary_estimates.append(
        {"source": "Market Estimate", "min": market["min"], "max": market["max"],
         "median": market["median"]}
    )
    sources_used.append("Market Estimate")

    # Aggregate
    all_mins = [s["min"] for s in salary_estimates]
    all_maxs = [s["max"] for s in salary_estimates]
    all_medians = [s["median"] for s in salary_estimates]

    agg_min = int(min(all_mins))
    agg_max = int(max(all_maxs))
    agg_median = int(sum(all_medians) / len(all_medians))

    confidence = min(0.95, 0.5 + len(sources_used) * 0.15)

    return {
        "estimated_range": f"${agg_min:,} - ${agg_max:,}",
        "min": agg_min,
        "max": agg_max,
        "median": agg_median,
        "confidence_score": round(confidence, 2),
        "sources_used": sources_used,
        "breakdown": {
            "base_salary": f"${agg_min:,} - ${int(agg_median * 1.05):,}",
            "bonus": "10-20% of base (varies)",
            "equity": market.get("total_comp_range", "Varies by company"),
            "total_comp": market.get("total_comp_range", f"${agg_min:,} - ${int(agg_max * 1.3):,}"),
        },
        "notes": market.get("notes", ""),
        "source_details": salary_estimates,
    }
