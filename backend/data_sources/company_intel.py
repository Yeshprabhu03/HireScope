"""
Company Intelligence: fetches company data from Wikipedia API and public sources.
"""
import logging
import httpx
import re
from typing import Optional
from urllib.parse import quote
from tenacity import retry, stop_after_attempt, wait_exponential

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

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False)
async def fetch_wikipedia_summary(company: str, sub_team: Optional[str] = None, is_retry: bool = False) -> Optional[dict]:
    """Fetch company summary from Wikipedia API."""
    # Resolve any known abbreviation first
    resolved_company = resolve_company_name(company)

    # Build a list of name variations to try
    suffixes_to_strip = [" Inc.", " LLC", " Corp.", " Corporation", " Holdings", " Group", " Ltd.", " Limited", ", Inc.", ", LLC", ", Holdings"]

    search_names = []
    # If sub_team is provided, try that first as a specific entity
    if "(company)" not in company and "(company)" not in (sub_team or ""):
        if sub_team and sub_team != "N/A":
            search_names.append(sub_team)
            search_names.append(f"{sub_team} (company)")
            search_names.append(f"{resolved_company} {sub_team}")

    # Original name and variations
    search_names.append(resolved_company)

    # Progressively strip suffixes iteratively
    name = resolved_company
    changed = True
    while changed:
        changed = False
        for suffix in suffixes_to_strip:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
                if name.endswith(","): # Strip trailing comma after stripping suffix
                    name = name[:-1].strip()
                changed = True
    if name != resolved_company and name not in search_names:
        search_names.append(name)

    search_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"

    async with httpx.AsyncClient() as client:
        # 1. New Search Pass: If sub_team is provided, use the Search API to find the best title
        if sub_team and sub_team != "N/A" and not is_retry:
            try:
                logger.info(f"Searching Wikipedia for specific sub-team: '{sub_team}' at {company}")
                search_api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(f'{company} {sub_team}')}&format=json"
                search_res = await client.get(search_api_url, headers={"User-Agent": "HireScope/1.0"}, timeout=10)
                if search_res.status_code == 200:
                    results = search_res.json().get("query", {}).get("search", [])
                    for result in results[:5]: # Try top 5 results for relevance
                        best_title = result["title"]
                        # Validate title: must contain company name or sub_team name to be considered
                        if (sub_team.lower() in best_title.lower() or
                            company.lower() in best_title.lower() or
                            (result == results[0] and len(best_title) > 0)):
                            if best_title.lower() != resolved_company.lower() and best_title not in search_names:
                                logger.info(f"Found specific Wikipedia title from search: '{best_title}'")
                                search_names.insert(0, best_title)
                                break # Found a good one
            except Exception as e:
                logger.warning(f"Wikipedia sub-team search failed: {e}")

        # 1b. Company Search Fallback: If direct lookups fail, try searching for the company name
        if not is_retry:
            try:
                search_api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(resolved_company)}&format=json"
                search_res = await client.get(search_api_url, headers={"User-Agent": "HireScope/1.0"}, timeout=10)
                if search_res.status_code == 200:
                    results = search_res.json().get("query", {}).get("search", [])
                    if results:
                        top_result = results[0]["title"]
                        if top_result not in search_names:
                            logger.info(f"Adding Wikipedia company search result: '{top_result}'")
                            search_names.append(top_result)
            except Exception as e:
                logger.warning(f"Wikipedia company search failed: {e}")

        for search_name in search_names:
            try:
                logger.info(f"Trying Wikipedia lookup for: '{search_name}'")
                response = await client.get(
                    f"{search_url}{quote(search_name.replace(' ', '_'))}",
                    headers={"User-Agent": "HireScope/1.0 (educational project)"},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()

                    # Check for disambiguation page
                    if data.get("type") == "disambiguation" and not is_retry:
                        logger.info(f"Hit disambiguation page for '{search_name}', retrying with ' (company)' suffix")
                        res = await fetch_wikipedia_summary(f"{search_name} (company)", sub_team=sub_team, is_retry=True)
                        if res: return res
                        continue # Try next candidate

                    raw_extract = data.get("extract", "")

                    # If we were looking for a specific sub-team, ensure the summary actually mentions it
                    if sub_team and sub_team != "N/A" and sub_team.lower() not in raw_extract.lower():
                        if search_name.lower() != resolved_company.lower():
                            logger.info(f"Summary for '{search_name}' doesn't mention sub-team '{sub_team}', skipping.")
                            continue

                    # Check for mismatched entity types
                    corporate_keywords = ["company", "corporation", "inc", "llc", "ltd", "business", "technology", "software", "bank", "financial", "firm", "enterprise", "subsidiary", "brand", "investment", "wealth", "asset", "service"]
                    if not is_retry and raw_extract and not any(kw in raw_extract.lower() for kw in corporate_keywords):
                        logger.info(f"Summary for '{search_name}' lacks corporate keywords. Retrying with ' (company)'.")
                        res = await fetch_wikipedia_summary(f"{search_name} (company)", sub_team=sub_team, is_retry=True)
                        if res: return res
                        continue # Try next candidate

                    return {
                        "description": raw_extract,
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


async def fetch_company_intel(company: str, role: str = "", parsed_jd: dict = None, sub_team: str = None, team_context: str = None, use_mock: bool = False, provider: str = "gemini") -> dict:
    """
    Fetch comprehensive company intelligence from Wikipedia and Gemini.
    """
    if use_mock:
        logger.info(f"Using mock company intel for '{company}'")
        return _mock_company_intel(company)

    intel = {
        "name": company,
        "description": "A prominent entity in the industry.",
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
        "revenue_breakdown": [],
        "org_chart_mermaid": "",
        "source": "Wikipedia API",
    }

    # 0. Fetch Glassdoor data via search/MCP logic
    try:
        from utils.glassdoor import get_glassdoor_data
        gd_data = await get_glassdoor_data(company)
        if gd_data and gd_data.get("rating") != 0:
            intel["glassdoor_rating"] = gd_data.get("rating")
            intel["glassdoor_review_count"] = gd_data.get("review_count")
            intel["glassdoor_pros"] = gd_data.get("pros", [])
            intel["glassdoor_cons"] = gd_data.get("cons", [])
            intel["glassdoor_url"] = gd_data.get("url")
            logger.info(f"Successfully integrated Glassdoor rating ({gd_data.get('rating')}) for '{company}'")
    except Exception as e:
        logger.warning(f"Could not fetch Glassdoor data for '{company}': {e}")

    # 1. Base info via Wikipedia
    # We now fetch TWO summaries if a sub-team is present to avoid one overwriting the other
    main_wiki = None
    sub_wiki = None

    try:
        # Fetch individual summaries
        main_wiki = await fetch_wikipedia_summary(company)
        if sub_team and sub_team != "N/A":
            sub_wiki = await fetch_wikipedia_summary(company, sub_team=sub_team)

        if main_wiki:
            intel["description"] = main_wiki.get("description", "")
            intel["wikipedia_url"] = main_wiki.get("wikipedia_url", "")
            intel["source"] = "Wikipedia API"
            logger.info(f"Fetched parent Wikipedia summary for '{company}'")

        if sub_wiki:
            # We don't overwrite the main description, but we log success
            logger.info(f"Fetched sub-team Wikipedia summary for '{sub_team}'")

        if not main_wiki and not sub_wiki:
            intel["description"] = f"A prominent company in its sector."
            logger.warning(f"Wikipedia fetch failed for both parent and sub-team.")
    except Exception as e:
        logger.warning(f"Wikipedia fetch failed: {e}")
        intel["description"] = f"A prominent company in its sector."

    # 2. Extract deep metrics and networking targets with LLM
    try:
        from config import settings
        from utils.llm import llm_generate_json

        bu = parsed_jd.get('business_unit', 'N/A') if parsed_jd else 'N/A'
        team_context = f" and specific team/brand '{sub_team}'" if sub_team else ""
        bu_context = f" The candidate is applying to the '{bu}' business unit{team_context}. " if bu and bu != 'N/A' else ""
        jd_context = f"\n\nContext - Job Description: {parsed_jd}" if parsed_jd else ""

        if settings.GEMINI_API_KEY != "placeholder":
            prompt = f"""Provide company intelligence for "{company}", specifically focusing on the "{sub_team or bu}" group.

Target Team/Group: {sub_team or 'N/A'}
Team Business Unit: {bu}
Job Role: {role}
{f"Extracted JD Team Context: {team_context}" if team_context else ""}

Research Context - Parent Company (Wikipedia):
{main_wiki.get('description', '')[:8000] if main_wiki else "N/A"}

Research Context - Target Sub-Team (Wikipedia):
{sub_wiki.get('description', '')[:8000] if sub_wiki else "N/A"}

{bu_context}{jd_context}

Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{{
  "description": "<A 2-3 sentence overview of the company's main business and global significance.>",
  "ceo": "<current CEO full name, or 'N/A' if unknown>",
  "founded": "<founding year, or 'N/A'>",
  "headquarters": "<City, State/Country, or 'N/A'>",
  "employees": "<approximate headcount, e.g. '~9,000' or 'N/A'>",
  "ticker": "<Stock ticker symbol if public, e.g. 'AAPL', 'MSFT', 'ADBE', or 'N/A' if private/unknown>",
  "industry": "<primary industry sector>",
  "business_model": "<1-2 sentences about how they make money>",
  "target_team_confirmed": "{sub_team or 'N/A'}",
  "business_unit_overview": "<MANDATORY: If 'target_team_confirmed' is not 'N/A', you MUST research and describe the specific '{sub_team}' group at {company}. Explain its history (e.g. Ayco was acquired in 2003), its specialized services, and why it is unique within the broader {company} structure.>",
  "linkedin_networking": "<1-2 sentences advising the user which specific organizational teams, directors, or managers they should try connecting with on LinkedIn for the '{role}' role>",
  "culture_highlights": ["<3-4 key culture traits based on known reputation>"],
  "recent_news": ["<2-3 real, verifiable recent events about this company>"],
  "revenue_breakdown": [
    {{"division": "<Name of major business division>", "revenue_percentage": "<Approx % of total revenue, e.g. '70%'>"}}
  ],
  "org_chart_mermaid": "<MANDATORY: A strictly valid Mermaid.js 'graph TD' string showing the hierarchy from top company levels down to business unit and role. Use ONLY [Name] for nodes. DO NOT wrap in code blocks. Example: 'graph TD; Google[Google]-->Ads[Ads Division]; Ads-->Eng[Engineering];'>"
}}
Use 'N/A' for any field you are not confident about. Do NOT invent data. If a revenue breakdown or org chart cannot be reasonably estimated, provide empty arrays or empty strings.
IMPORTANT: The org_chart_mermaid must be a single string without markdown formatting."""

            ai_data = await llm_generate_json(prompt, provider=provider, max_tokens=900, temperature=0.0)

            # Cleanup Mermaid string
            if "org_chart_mermaid" in ai_data:
                m_str = ai_data["org_chart_mermaid"]
                # 1. Strip potential markdown blocks
                m_str = re.sub(r"```mermaid\s*", "", m_str)
                m_str = re.sub(r"```\s*", "", m_str)
                m_str = m_str.strip()

                # 2. Add 'graph TD;' if missing
                if m_str and not (m_str.startswith("graph") or m_str.startswith("flowchart")):
                    m_str = f"graph TD; {m_str}"

                # 3. Robust fix: Remove problematic characters and ensure basic graph structure
                m_str = m_str.replace("&", "and").replace("(", "[").replace(")", "]")
                # Remove any nested markdown if the LLM was stubborn
                m_str = re.sub(r"\[+([^\[\]]+)\]+", r"[\1]", m_str)

                # Final assignment
                ai_data["org_chart_mermaid"] = m_str
                logger.info(f"Generated Sanitized Mermaid: {m_str}")

            # Fetch real-time market cap using Yahoo Finance
            ticker = ai_data.get("ticker", "N/A")
            market_cap_str = "Not Listed / Private" if not ticker or ticker.upper() == "N/A" else "N/A"
            if ticker and ticker.upper() != "N/A":
                try:
                    import yfinance as yf
                    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
                    def _fetch_mcap(t):
                        stock = yf.Ticker(t)
                        return stock.info.get("marketCap")

                    mcap = _fetch_mcap(ticker)
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
