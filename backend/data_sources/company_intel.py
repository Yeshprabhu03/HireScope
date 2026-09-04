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


async def fetch_wikidata_employees(wikipedia_page_title: str) -> Optional[str]:
    """
    Fetch up-to-date employee count from Wikidata (P1128) for a given Wikipedia page title.
    Returns a formatted string like '~2,500' or None if unavailable.
    """
    try:
        async with httpx.AsyncClient() as client:
            # Step 1: Get Wikidata item ID (QID) from the Wikipedia page
            r = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": wikipedia_page_title,
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "format": "json",
                },
                headers={"User-Agent": "HireScope/1.0"},
                timeout=10,
            )
            pages = r.json().get("query", {}).get("pages", {})
            qid = None
            for page in pages.values():
                qid = page.get("pageprops", {}).get("wikibase_item")
                break

            if not qid:
                logger.info(f"No Wikidata QID found for Wikipedia page '{wikipedia_page_title}'")
                return None

            logger.info(f"Found Wikidata QID {qid} for '{wikipedia_page_title}'")

            # Step 2: Fetch P1128 (number of employees) claim from Wikidata
            r2 = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": qid,
                    "props": "claims",
                    "format": "json",
                },
                headers={"User-Agent": "HireScope/1.0"},
                timeout=10,
            )
            claims = r2.json().get("entities", {}).get(qid, {}).get("claims", {})
            emp_claims = claims.get("P1128", [])
            if not emp_claims:
                logger.info(f"Wikidata has no P1128 (employees) claim for QID {qid}")
                return None

            # Pick the most recent preferred or normal rank claim
            best = None
            for claim in emp_claims:
                if claim.get("rank") == "preferred":
                    best = claim
                    break
            if best is None:
                best = emp_claims[-1]  # Fall back to last entry (usually most recent)

            amount = (
                best.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                    .get("amount")
            )
            if amount:
                n = int(float(str(amount).lstrip("+")))
                formatted = f"{n:,}"
                logger.info(f"Wikidata employee count for '{wikipedia_page_title}': {formatted}")
                return formatted

    except Exception as e:
        logger.warning(f"Wikidata employees lookup failed for '{wikipedia_page_title}': {e}")
    return None


def resolve_ticker_from_name(company_name: str) -> Optional[str]:
    """
    Resolve a stock ticker from a company name via Yahoo Finance's search API.

    The LLM often can't supply a ticker for recently-IPO'd companies (e.g.
    ServiceTitan / TTAN, public since Dec 2024 but after most model cutoffs),
    which left the report showing 'Not Listed / Private'. This lookup fills that
    gap using live market data instead of the model's stale knowledge.
    """
    if not company_name or company_name.strip().lower() in ("", "unknown", "n/a"):
        return None
    try:
        import requests
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": company_name, "quotesCount": 5, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/120.0.0.0 Safari/537.36"},
            timeout=8,
        )
        resp.raise_for_status()
        for q in resp.json().get("quotes", []):
            if q.get("quoteType") == "EQUITY" and q.get("symbol"):
                logger.info(f"Resolved ticker '{q['symbol']}' for '{company_name}' via Yahoo search")
                return q["symbol"]
    except Exception as e:
        logger.warning(f"Yahoo ticker search failed for '{company_name}': {e}")
    return None


def _format_market_cap(usd: float) -> str:
    if usd >= 1e12:
        return f"${usd / 1e12:.2f}T"
    if usd >= 1e9:
        return f"${usd / 1e9:.2f}B"
    return f"${usd / 1e6:.2f}M"


def fetch_market_cap_finnhub(company_name: str, ticker: Optional[str] = None) -> Optional[tuple]:
    """
    Resolve (market_cap_str, ticker) via Finnhub, which works reliably from
    cloud IPs (Yahoo returns 429 on Railway). Returns None if unavailable —
    the caller then falls back to Yahoo. Requires FINNHUB_API_KEY.
    """
    from config import settings
    key = settings.FINNHUB_API_KEY
    if not key or key == "placeholder":
        return None
    import requests
    try:
        # Resolve a ticker if the LLM didn't supply one.
        if not ticker or ticker.upper() == "N/A":
            r = requests.get(
                "https://finnhub.io/api/v1/search",
                params={"q": company_name, "token": key},
                timeout=8,
            )
            r.raise_for_status()
            for item in r.json().get("result", []):
                sym = item.get("symbol", "")
                # Prefer plain US symbols (skip exchange-suffixed foreign listings).
                if sym and "." not in sym and ":" not in sym:
                    ticker = sym
                    break
            if not ticker or ticker.upper() == "N/A":
                return None

        # profile2.marketCapitalization is reported in MILLIONS of USD.
        r = requests.get(
            "https://finnhub.io/api/v1/stock/profile2",
            params={"symbol": ticker, "token": key},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        mcap_millions = data.get("marketCapitalization")
        if mcap_millions:
            resolved = data.get("ticker") or ticker
            logger.info(f"Finnhub market cap for '{company_name}' ({resolved}): {mcap_millions}M USD")
            return (_format_market_cap(mcap_millions * 1e6), resolved)
    except Exception as e:
        logger.warning(f"Finnhub market cap lookup failed for '{company_name}' ({ticker}): {e}")
    return None


# --- SEC EDGAR: real annual revenue from 10-K XBRL data (no API key needed) ---
_SEC_TICKER_MAP = None  # module-level cache of the ticker -> CIK map

def _sec_headers() -> dict:
    # SEC requires a descriptive User-Agent identifying the caller.
    return {"User-Agent": "HireScope/1.0 (job-intelligence tool; admin@hirescope.app)"}


def _sec_cik_for_ticker(ticker: str) -> Optional[str]:
    global _SEC_TICKER_MAP
    import requests
    try:
        if _SEC_TICKER_MAP is None:
            r = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=_sec_headers(), timeout=10,
            )
            r.raise_for_status()
            _SEC_TICKER_MAP = {
                v["ticker"].upper(): str(v["cik_str"]).zfill(10)
                for v in r.json().values()
            }
        return _SEC_TICKER_MAP.get(ticker.upper())
    except Exception as e:
        logger.warning(f"SEC ticker->CIK lookup failed for '{ticker}': {e}")
        return None


def fetch_sec_revenue(ticker: str) -> Optional[dict]:
    """
    Fetch real annual revenue from SEC EDGAR's XBRL companyconcept API.
    Returns {'total', 'fiscal_year', 'prior_total', 'yoy'} or None. No key needed.
    """
    if not ticker or ticker.upper() == "N/A":
        return None
    cik = _sec_cik_for_ticker(ticker)
    if not cik:
        return None
    import requests
    from datetime import date
    # Revenue is tagged under several us-gaap concepts depending on filing era.
    concepts = [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ]
    for concept in concepts:
        try:
            r = requests.get(
                f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json",
                headers=_sec_headers(), timeout=10,
            )
            if r.status_code != 200:
                continue
            units = r.json().get("units", {}).get("USD", [])
            by_end = {}
            for u in units:
                if u.get("form") != "10-K":
                    continue
                start, end, val = u.get("start"), u.get("end"), u.get("val")
                if not (start and end and val is not None):
                    continue
                try:
                    days = (date.fromisoformat(end) - date.fromisoformat(start)).days
                except Exception:
                    continue
                if 330 <= days <= 400:  # keep full-year periods only
                    by_end[end] = (val, u.get("fy"))
            if not by_end:
                continue
            ordered = sorted(by_end.items(), key=lambda x: x[0], reverse=True)
            latest_end, (latest_val, latest_fy) = ordered[0]
            result = {"total": latest_val, "fiscal_year": latest_fy or latest_end[:4]}
            if len(ordered) > 1:
                prior_val = ordered[1][1][0]
                result["prior_total"] = prior_val
                if prior_val:
                    result["yoy"] = round((latest_val - prior_val) / prior_val * 100, 1)
            logger.info(f"SEC revenue for {ticker} (CIK {cik}, {concept}): {latest_val} FY{result['fiscal_year']}")
            return result
        except Exception as e:
            logger.warning(f"SEC revenue lookup ({concept}) failed for {ticker}: {e}")
            continue
    return None


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

    # Company-level facts (Wikipedia/Wikidata/market cap) are role-independent, so
    # cache them by company. Analyzing several roles at the same company then skips
    # these external fetches and only re-runs the role-specific LLM enrichment.
    from datetime import datetime, timedelta
    from database import get_company_snapshot, save_company_snapshot
    from config import settings as _settings
    facts_key = f"{_settings.COMPANY_CACHE_VERSION}::facts::{company}"
    cached_facts = None
    if company and company != "Unknown":
        try:
            snap = await get_company_snapshot(facts_key)
            if snap and snap.get("data"):
                raw = snap.get("snapshot_date")
                d = raw if isinstance(raw, datetime) else (datetime.fromisoformat(raw) if raw else None)
                if d and datetime.now() - d < timedelta(days=30):
                    cached_facts = snap["data"]
                    logger.info(f"Using cached company-level facts for '{company}'")
        except Exception as e:
            logger.warning(f"Company facts cache read failed for '{company}': {e}")

    # 1. Base info via Wikipedia + Wikidata structured employee count
    # We now fetch TWO summaries if a sub-team is present to avoid one overwriting the other
    main_wiki = None
    sub_wiki = None
    wikidata_employees: Optional[str] = None

    if cached_facts:
        # Reuse role-independent facts; only the (role-specific) sub-team summary
        # is still fetched live when a sub_team is present.
        intel["description"] = cached_facts.get("description") or intel["description"]
        intel["wikipedia_url"] = cached_facts.get("wikipedia_url", "")
        intel["source"] = cached_facts.get("source", "Wikipedia API")
        wikidata_employees = cached_facts.get("employees")
        if wikidata_employees:
            intel["employees"] = wikidata_employees
        # Reconstruct main_wiki so the LLM prompt still has the company description
        main_wiki = {"description": intel["description"], "wikipedia_url": intel.get("wikipedia_url", "")}
        if sub_team and sub_team != "N/A":
            try:
                sub_wiki = await fetch_wikipedia_summary(company, sub_team=sub_team)
            except Exception as e:
                logger.warning(f"Sub-team Wikipedia fetch failed: {e}")
    else:
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

                # Derive page title from the Wikipedia URL for the Wikidata lookup
                wiki_url = main_wiki.get("wikipedia_url", "")
                page_title = wiki_url.rstrip("/").split("/wiki/")[-1].replace("_", " ") if "/wiki/" in wiki_url else resolve_company_name(company)
                wikidata_employees = await fetch_wikidata_employees(page_title)
                if wikidata_employees:
                    intel["employees"] = wikidata_employees

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
        from pydantic import BaseModel, Field
        from typing import List

        class RevenueBreakdown(BaseModel):
            division: str = Field(description="Name of major business division")
            revenue_percentage: str = Field(description="Approx % of total revenue, e.g. '70%'")

        class CompanyIntel(BaseModel):
            description: str = Field(description="A 2-3 sentence overview of the company's main business and global significance.")
            ceo: str = Field(description="current CEO full name, or 'N/A' if unknown")
            founded: str = Field(description="founding year, or 'N/A'")
            headquarters: str = Field(description="City, State/Country, or 'N/A'")
            employees: str = Field(description="approximate headcount, e.g. '~9,000' or 'N/A'")
            ticker: str = Field(description="Stock ticker symbol if public, e.g. 'AAPL', 'MSFT', 'ADBE', or 'N/A' if private/unknown")
            industry: str = Field(description="primary industry sector")
            business_model: str = Field(description="1-2 sentences about how they make money")
            target_team_confirmed: str = Field(description="Reflect the requested sub_team or 'N/A'")
            business_unit_overview: str = Field(description="MANDATORY: If target_team_confirmed is not N/A, describe the specific group history and specialty.")
            linkedin_networking: str = Field(description="1-2 sentences advising the user which specific organizational teams, directors, or managers they should try connecting with on LinkedIn for the role")
            culture_highlights: List[str] = Field(description="3-4 key culture traits based on known reputation")
            recent_news: List[str] = Field(description="2-3 real, verifiable recent events about this company")
            revenue_breakdown: List[RevenueBreakdown] = Field(description="Revenue breakdown by division")
            org_chart_mermaid: str = Field(description="MANDATORY: A strictly valid Mermaid.js 'graph TD' string showing the hierarchy from top company levels down to business unit and role. Use ONLY [Name] for nodes. DO NOT wrap in code blocks. Example: 'graph TD; Google[Google]-->Ads[Ads Division]; Ads-->Eng[Engineering];'")

        bu = parsed_jd.get('business_unit', 'N/A') if parsed_jd else 'N/A'
        team_context = f" and specific team/brand '{sub_team}'" if sub_team else ""
        bu_context = f" The candidate is applying to the '{bu}' business unit{team_context}. " if bu and bu != 'N/A' else ""
        jd_context = f"\n\nContext - Job Description: {parsed_jd}" if parsed_jd else ""

        # Gate on the ACTIVE provider's key, not Gemini specifically — otherwise
        # switching to OpenAI silently skips company enrichment (CEO/HQ/market cap).
        provider_key = {
            "gemini": settings.GEMINI_API_KEY,
            "openai": settings.OPENAI_API_KEY,
            "anthropic": settings.ANTHROPIC_API_KEY,
        }.get(provider, "placeholder")

        if provider_key != "placeholder":
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

Use 'N/A' only for specific facts you genuinely don't know (e.g. a private company's CEO). Do NOT fabricate precise figures.

However, for well-known public companies you SHOULD provide a best-effort revenue_breakdown using widely-reported public segment information — approximate percentages by major division/segment are expected (e.g. for Salesforce: Subscription & Support vs Professional Services, or by cloud: Sales/Service/Platform/Marketing & Commerce/Data). Mark them as approximate rather than leaving the array empty. Only return an empty revenue_breakdown array if the company is private/obscure with no public segment data. Likewise, always produce a plausible org_chart_mermaid from the company down to the target team/role.
IMPORTANT: The org_chart_mermaid must be a single string without markdown formatting."""

            # The CompanyIntel schema is large (overview, culture list, news,
            # revenue breakdown, Mermaid org chart) — 900 tokens truncated it.
            ai_data = await llm_generate_json(prompt, provider=provider, max_tokens=3000, temperature=0.0, response_schema=CompanyIntel)

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

            # Market cap: reuse cached value, else resolve ticker + fetch live.
            ticker = ai_data.get("ticker", "N/A")
            # Only reuse a cached REAL market cap ($...); never a transient
            # failure or the misleading "Not Listed / Private" verdict.
            if cached_facts and str(cached_facts.get("market_cap", "")).startswith("$"):
                market_cap_str = cached_facts["market_cap"]
                ticker = cached_facts.get("ticker") or ticker
                if ticker and ticker != "N/A":
                    ai_data["ticker"] = ticker
                logger.info(f"Using cached market cap for '{company}': {market_cap_str}")
            else:
                # Default to a neutral "N/A" — we can't assert a company is
                # private just because a (rate-limited) lookup gave no ticker.
                market_cap_str = "N/A"

                # Primary source: Finnhub (reliable from cloud IPs). It also
                # resolves the ticker for post-cutoff IPOs the LLM misses.
                fh = fetch_market_cap_finnhub(company, ticker)
                if fh:
                    market_cap_str, ticker = fh
                    ai_data["ticker"] = ticker
                    intel["source"] = "Wikipedia + Finnhub"

                # Fallback: Yahoo (works locally; 429-limited on Railway).
                if market_cap_str == "N/A":
                    if not ticker or ticker.upper() == "N/A":
                        resolved = resolve_ticker_from_name(company)
                        if resolved:
                            ticker = resolved
                            ai_data["ticker"] = resolved
                    if ticker and ticker.upper() != "N/A":
                        try:
                            import yfinance as yf
                            @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=5), reraise=True)
                            def _fetch_mcap(t):
                                stock = yf.Ticker(t)
                                return stock.info.get("marketCap")

                            mcap = _fetch_mcap(ticker)
                            if mcap:
                                market_cap_str = _format_market_cap(mcap)
                                intel["source"] = "Wikipedia + Yahoo Finance"
                        except Exception as e:
                            logger.warning(f"yfinance failed to fetch market cap for {ticker}: {e}")

            ai_data["market_cap"] = market_cap_str
            intel.update(ai_data)

            # Real annual revenue from SEC EDGAR (role-independent; cached with facts).
            if cached_facts and cached_facts.get("revenue_total"):
                intel["revenue_total"] = cached_facts.get("revenue_total")
                intel["revenue_fiscal_year"] = cached_facts.get("revenue_fiscal_year")
                intel["revenue_yoy"] = cached_facts.get("revenue_yoy")
            elif ticker and ticker.upper() != "N/A":
                sec_rev = fetch_sec_revenue(ticker)
                if sec_rev:
                    intel["revenue_total"] = sec_rev.get("total")
                    intel["revenue_fiscal_year"] = sec_rev.get("fiscal_year")
                    intel["revenue_yoy"] = sec_rev.get("yoy")

            # Always trust the authoritative Wikidata employee count over LLM inference
            if wikidata_employees:
                intel["employees"] = wikidata_employees
                logger.info(f"Restored authoritative Wikidata employee count: {wikidata_employees}")
            logger.info(f"Enhanced company intel for '{company}' via {provider}")

    except Exception as e:
        logger.warning(f"Company enrichment failed: {e}")

    # Persist role-independent company facts for reuse across other roles.
    if company and company != "Unknown" and not cached_facts and main_wiki:
        try:
            mc = intel.get("market_cap")
            await save_company_snapshot(facts_key, {
                "description": intel.get("description"),
                "wikipedia_url": intel.get("wikipedia_url", ""),
                "source": intel.get("source", "Wikipedia API"),
                "employees": intel.get("employees") if intel.get("employees") != "N/A" else None,
                "ticker": intel.get("ticker") if intel.get("ticker") not in (None, "N/A") else None,
                # Only cache a real resolved value ($...); a failed/unavailable
                # lookup stays uncached so it retries on the next analysis.
                "market_cap": mc if (mc and str(mc).startswith("$")) else None,
                "revenue_total": intel.get("revenue_total"),
                "revenue_fiscal_year": intel.get("revenue_fiscal_year"),
                "revenue_yoy": intel.get("revenue_yoy"),
            })
            logger.info(f"Cached company-level facts for '{company}'")
        except Exception as e:
            logger.warning(f"Company facts cache write failed for '{company}': {e}")

    return intel
