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
    """Extract numeric salary range from free text. Handles multiple formats like $76,600.00/yr."""
    if not salary_text:
        return None

    # Clean the string slightly for easier matching: remove periodic labels that confuse simple ranges
    # but keep them for 'k' detection if needed.
    # e.g. "$76,600.00/yr" -> "$76,600.00"
    clean_text = re.sub(r'/(?:yr|hr|year|hour|annually|mo|month)', '', salary_text, flags=re.I)

    # Pattern 1: $180,000 - $250,000 or $180K-$250K (handles decimals)
    pattern1 = r"\$?([\d,]+(?:\.\d+)?)[kK]?\s*[-–to]+\s*\$?([\d,]+(?:\.\d+)?)[kK]?"
    # Pattern 2: between $63,000 and $93,000
    pattern2 = r"between\s+\$?([\d,]+(?:\.\d+)?)[kK]?\s+and\s+\$?([\d,]+(?:\.\d+)?)[kK]?"
    # Pattern 3: from $X to $Y
    pattern3 = r"from\s+\$?([\d,]+(?:\.\d+)?)[kK]?\s+to\s+\$?([\d,]+(?:\.\d+)?)[kK]?"

    for pattern in [pattern2, pattern3, pattern1]:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            try:
                low_raw = match.group(1).replace(",", "")
                high_raw = match.group(2).replace(",", "")
                low = float(low_raw)
                high = float(high_raw)

                # Handle 'k' multiplier
                if "k" in salary_text.lower() and low < 1000:
                    low *= 1000
                    high *= 1000

                # Sanity check: if it's an hourly rate (e.g. 50-70), we don't treat it as 50k-70k
                # unless 'k' was explicit. But for now, HireScope assumes annual if > 5000.
                # If it's small (like 50-100), it's likely hourly.
                if low < 500: # Very likely hourly or invalid for this tool's annual focus
                    return None

                return {"min": int(low), "max": int(high)}
            except (ValueError, IndexError):
                continue
    return None


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
async def estimate_market_salary_with_claude(
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

        return await llm_generate_json(prompt, provider=provider, max_tokens=500, temperature=0.0)

    except Exception as e:
        logger.error(f"Gemini salary estimation failed: {e}", exc_info=True)
        return {"min": 120000, "max": 200000, "median": 160000, "notes": "Estimate unavailable"}


async def analyze_salary(
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
        historical = await get_historical_salary(company, job_title, location)
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

    # Source 3: LLM market estimate
    # IMPORTANT: Only run if there's no explicit JD disclosure.
    # If the company published a salary range, that's the ground truth — don't let an LLM estimate inflate it.
    market = await estimate_market_salary_with_claude(
        job_title, company, location, seniority_level, required_skills, jd_text_snippet=jd_text_snippet, use_mock=use_mock, provider=provider
    )
    if not jd_salary:
        # No JD disclosure — use market estimate as the primary source
        salary_estimates.append(
            {"source": "Market Estimate", "min": market["min"], "max": market["max"],
             "median": market["median"]}
        )
        sources_used.append("Market Estimate")
    else:
        # JD disclosed a salary — use market estimate for context only in notes, not in the range
        logger.info(f"JD disclosed salary ${jd_salary['min']:,}-${jd_salary['max']:,}. Using it as authoritative range (market estimate suppressed from aggregation).")

    # Aggregate
    all_mins = [s["min"] for s in salary_estimates]
    all_maxs = [s["max"] for s in salary_estimates]
    all_medians = [s["median"] for s in salary_estimates]

    if jd_salary:
        # JD disclosed salary = authoritative base range
        agg_min = jd_salary["min"]
        agg_max = jd_salary["max"]
        agg_median = (agg_min + agg_max) // 2
    else:
        # No disclosure — average all available sources
        agg_min = int(sum(all_mins) / len(all_mins))
        agg_max = int(sum(all_maxs) / len(all_maxs))
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
            "base_salary": f"${agg_min:,} - ${agg_max:,}" + (" (as disclosed in JD)" if jd_salary else ""),
            "bonus": f"${bonus_low:,} - ${bonus_high:,}  (10–20% of base)",
            "equity": f"${equity_low:,} - ${equity_high:,} / yr  (RSUs, 4-yr vest)",
            "total_comp": f"${total_low:,} - ${total_high:,}",
        },
        "notes": (f"Base salary as disclosed in job description. " if jd_salary else "") + market.get("notes", ""),
        "source_details": salary_estimates,
    }
