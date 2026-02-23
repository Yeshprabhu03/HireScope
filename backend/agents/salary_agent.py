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
    jd_text_snippet: Optional[str] = None,
    use_mock: bool = False,
    provider: str = "gemini",
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
        from utils.llm import llm_generate_json

        context_block = f"\n\nContext - Raw Job Description Snippet:\n{jd_text_snippet}" if jd_text_snippet else ""
        
        prompt = f"""You are a compensation expert. Estimate the salary range for this position.

Job Title: {job_title}
Company: {company}
Location: {location}
Seniority: {seniority}
Key Skills: {", ".join(skills[:10])}{context_block}

Return ONLY valid JSON with this structure:
{{
  "min": <integer annual salary USD>,
  "max": <integer annual salary USD>,
  "median": <integer annual salary USD>,
  "base_range": "<string like '$X - $Y'>",
  "total_comp_range": "<string including equity/bonus>",
  "notes": "<brief 1-2 sentence explanation>"
}}"""

        return llm_generate_json(prompt, provider=provider, max_tokens=500, temperature=0.0)

    except Exception as e:
        logger.error(f"Gemini salary estimation failed: {e}", exc_info=True)
        return {"min": 120000, "max": 200000, "median": 160000, "notes": "Estimate unavailable"}


def analyze_salary(
    job_title: str,
    company: str,
    location: str,
    seniority_level: str,
    required_skills: list[str],
    salary_mentioned: Optional[str],
    jd_text_snippet: Optional[str] = None,
    use_mock: bool = False,
    provider: str = "gemini",
) -> dict:
    """
    Triangulate salary from 3 sources and return unified intelligence.
    """
    if use_mock:
        return MOCK_SALARY_INTELLIGENCE

    sources_used = []
    salary_estimates = []

    # NEW: Source 0: HireScope Historical Database
    try:
        from database import get_historical_salary
        historical = get_historical_salary(company, job_title, location)
        if historical:
            # We have enough proprietary observations to trust this more than H1B
            logger.info(f"[{company}] Found {historical['count']} historical salary observations for '{job_title}'")
            salary_estimates.append({
                "source": "HireScope Historical Data", 
                "min": historical["avg_min"], 
                "max": historical["avg_max"], 
                "median": (historical["avg_min"] + historical["avg_max"]) // 2
            })
            sources_used.append(f"HireScope Historical Data ({historical['count']} verified postings)")
    except Exception as e:
        logger.warning(f"Historical salary lookup failed: {e}")

    # Source 1: DOL H1B data (Fallback if we don't have enough proprietary data, or add to blend)
    h1b_count = 0
    h1b_median_val = None
    try:
        from config import settings
        from data_sources.dol_h1b import load_h1b_data, get_salary_data

        df = load_h1b_data(settings.DOL_H1B_DATA_PATH)
        h1b_data = get_salary_data(df, job_title, company, location)
        h1b_count = h1b_data.get("count", 0)
        h1b_median_val = h1b_data.get("median")
        
        if h1b_count > 0:
            salary_estimates.append(
                {"source": "DOL H1B", "min": h1b_data["min"], "max": h1b_data["max"], "median": h1b_data["median"]}
            )
            sources_used.append(f"DOL H1B Data ({h1b_count} filings)")
        else:
            logger.info(f"No H1B filings found for '{job_title}' at '{company}'")
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
        job_title, company, location, seniority_level, required_skills, jd_text_snippet=jd_text_snippet, use_mock=use_mock, provider=provider
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

    # Confidence: 0.45 (AI only) → +0.20 for JD mention → +0.25 for H1B data
    confidence = 0.45
    if any("JD Mention" in s for s in sources_used):
        confidence += 0.20
    if h1b_count > 0:
        confidence += 0.25 + min(0.05, h1b_count * 0.002)  # more filings → higher confidence
    confidence = round(min(0.95, confidence), 2)

    # Label when using AI estimate only
    data_label = "Estimated (no H1B filings found)" if h1b_count == 0 else f"Based on {h1b_count} H1B filing(s)"

    # Handle IB-specific bonuses which are radically different from Tech RSUs
    is_ib = bool("investment banking" in job_title.lower() or "m&a" in job_title.lower() or "private equity" in job_title.lower())
    
    if is_ib:
        if "vice president" in seniority_level.lower() or "vp" in seniority_level.lower():
            agg_min, agg_max, agg_median = 250000, 350000, 300000
        elif "associate" in seniority_level.lower():
            agg_min, agg_max, agg_median = 175000, 225000, 200000
        elif "director" in seniority_level.lower() or "md" in seniority_level.lower():
            agg_min, agg_max, agg_median = 400000, 600000, 500000
        else: # analyst
            agg_min, agg_max, agg_median = 100000, 150000, 125000
            
        bonus_low = int(agg_min * 0.50)
        bonus_high = int(agg_median * 1.50)
        # IB rarely has heavy standard RSUs below MD level compared to base/bonus
        equity_low = 0
        equity_high = 0
    else:
        # Standard Tech/Corp roles
        bonus_low = int(agg_min * 0.10)
        bonus_high = int(agg_median * 0.20)
        equity_low = int(agg_min * 0.10)
        equity_high = int(agg_median * 0.25)
        
    total_low = agg_min + bonus_low + equity_low
    total_high = agg_max + bonus_high + equity_high

    return {
        "estimated_range": f"${agg_min:,} - ${agg_max:,}",
        "min": agg_min,
        "max": agg_max,
        "median": agg_median,
        "confidence_score": confidence,
        "data_label": data_label,
        "sources_used": sources_used,
        "breakdown": {
            "base_salary": f"${agg_min:,} - ${agg_max:,}",
            "bonus": f"${bonus_low:,} - ${bonus_high:,}  (10–20% of base)",
            "equity": f"${equity_low:,} - ${equity_high:,} / yr  (RSUs, 4-yr vest)",
            "total_comp": f"${total_low:,} - ${total_high:,}",
        },
        "notes": market.get("notes", ""),
        "source_details": salary_estimates,
    }
