"""
Fetch raw HTML from job posting URLs.
Supports LinkedIn, Greenhouse, Lever, Workday, Eightfold, Indeed and generic URLs.
Uses Playwright for JavaScript-rendered sites, requests for static sites.
"""
import logging
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Domains that require a real browser (JS-rendered SPAs)
JS_RENDERED_DOMAINS = [
    "eightfold.ai",
    "workday.com",
    "myworkdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "smartrecruiters.com",
    "icims.com",
]

# Domains that block all automated access — fail fast with a helpful message.
BLOCKED_DOMAINS: dict[str, str] = {
    # Removed linkedin.com block to allow public page fetching
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

MOCK_JOB_HTML = """
<html>
<body>
<h1>Senior Software Engineer</h1>
<h2>Google</h2>
<p>Location: Mountain View, CA (Hybrid)</p>
<p>We are looking for a Senior Software Engineer to join our team.</p>
<h3>Responsibilities</h3>
<ul>
  <li>Design, develop, and maintain scalable software systems</li>
  <li>Lead technical discussions and code reviews</li>
  <li>Collaborate with cross-functional teams</li>
  <li>Mentor junior engineers</li>
</ul>
<h3>Requirements</h3>
<ul>
  <li>5+ years of experience in software engineering</li>
  <li>Proficiency in Python, Java, or Go</li>
  <li>Experience with distributed systems</li>
  <li>Strong problem-solving skills</li>
  <li>BS/MS in Computer Science or equivalent</li>
</ul>
<h3>Compensation</h3>
<p>Salary: $180,000 - $250,000 per year</p>
<p>Benefits: Health, dental, vision, 401k, stock options</p>
<p>Remote: Hybrid (3 days in office)</p>
</body>
</html>
"""


def _needs_browser(url: str) -> bool:
    """Return True if the URL requires a real browser to render."""
    return any(domain in url for domain in JS_RENDERED_DOMAINS)


def _check_blocked(url: str) -> None:
    """Raise ValueError immediately for domains that block all automated access."""
    for domain, message in BLOCKED_DOMAINS.items():
        if domain in url:
            raise ValueError(message)


def _normalize_linkedin_url(url: str) -> str:
    """
    Convert LinkedIn collection URLs to direct job view URLs.
    e.g. .../jobs/collections/top-applicant/?currentJobId=12345
      -> .../jobs/view/12345
    """
    if "linkedin.com" in url and "currentJobId=" in url:
        import re
        match = re.search(r'currentJobId=(\d+)', url)
        if match:
            job_id = match.group(1)
            direct_url = f"https://www.linkedin.com/jobs/view/{job_id}"
            logger.info(f"Converted LinkedIn collection URL to direct URL: {direct_url}")
            return direct_url
    return url


def _detect_login_wall(html: str, url: str) -> bool:
    """Detect if the fetched page is a login/authentication wall."""
    login_indicators = [
        "Sign in",
        "Join now",
        "authwall",
        "login-form",
        "sign-in-form",
        "Create your free account",
        "Log in or sign up",
    ]
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text()
    title = soup.title.string if soup.title else ""

    if title and any(indicator.lower() in title.lower() for indicator in ["Sign In", "Log In", "Join"]):
        # If it's a linkedin public job, the title is usually "Company hiring Role..."
        # An actual authwall title is exactly "LinkedIn Login, Sign in | LinkedIn"
        if "linkedin.com" in url and ("hiring" in title.lower() or "jobs" in title.lower()):
            pass # Keep going, it's a real job posting
        else:
            return True

    indicator_count = sum(1 for ind in login_indicators if ind.lower() in text.lower())
    
    # LinkedIn public pages naturally have "Sign in" and "Join now" in the header nav
    threshold = 3 if "linkedin.com" in url else 2
    if indicator_count >= threshold:
        # One last safety check: if the schema or og:title exists with a real job, don't block it
        if "linkedin.com" in url and soup.find("meta", property="og:title"):
            og_title = soup.find("meta", property="og:title").get("content", "")
            if "hiring" in og_title.lower() or "job" in og_title.lower():
                return False
        return True

    return False


def fetch_job_html_with_cloudscraper(url: str) -> str:
    """
    Fallback fetcher using cloudscraper to bypass basic Cloudflare/Imperva 403 blocks
    without needing a full headless browser.
    """
    logger.info(f"Using Cloudscraper fallback for: {url}")
    import cloudscraper
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'desktop': True
        }
    )
    response = scraper.get(url, timeout=15)
    response.raise_for_status()
    html = response.text
    if len(html) < 500:
        logger.warning(f"Cloudscraper fetched very short content ({len(html)} chars) from {url}")
    else:
        logger.info(f"Cloudscraper fetched {len(html)} chars from {url}")
    return html


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
def fetch_job_html(url: str) -> str:
    """
    Fetch HTML content from a job posting URL.
    Uses requests for all pages, with advanced headers.
    Retries up to 2 times with exponential backoff.
    """
    logger.info(f"Fetching job HTML from: {url}")
    
    def _fetch_with_requests():
        try:
            print(f"Fallback to requests for {url}")
            session = requests.Session()
            session.headers.update(HEADERS)
            print("Sending GET request...")
            response = session.get(url, timeout=15)
            print("GET request completed. Checking status...")
            response.raise_for_status()
            logger.info(f"Successfully fetched HTML via requests ({len(response.text)} chars)")
            return response.text
        except requests.exceptions.HTTPError as e:
            if response.status_code in [403, 429]:
                logger.warning(f"HTTP {response.status_code} fetching {url}. Falling back to Cloudscraper...")
                try:
                    return fetch_job_html_with_cloudscraper(url)
                except Exception as scraper_err:
                    logger.error(f"Cloudscraper also blocked: {scraper_err}")
                    raise ValueError(f"Access Denied: The company's firewall (Akamai/Cloudflare) is strictly blocking HireScope's AI from reading this URL ({response.status_code}).")
            logger.warning(f"HTTP error fetching {url}: {e}")
            raise ValueError(f"Failed to fetch job posting: {response.status_code} Error")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error fetching {url}: {e}")
            raise ValueError(f"Failed to connect to the job URL. The site might be down.")
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout fetching {url}: {e}")
            raise ValueError(f"The job posting took too long to respond and timed out.")

    # Try requests first. If it gets 403/429, the except block will trigger Playwright.
    return _fetch_with_requests()



def extract_text_from_html(html: str) -> str:
    """Extract clean text content from HTML, removing scripts and styles."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    # Remove excessive blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def get_job_content(url: str, use_mock: bool = False) -> tuple[str, str]:
    """
    Fetch job posting and return (html, text) tuple.
    Raises ValueError immediately for domains that block automated access.
    Falls back to mock data only when use_mock=True (dev/test mode).
    """
    if use_mock:
        logger.info("Using mock job HTML data")
        html = MOCK_JOB_HTML
        return html, extract_text_from_html(html)

    # Fail fast with a clear message for blocked domains (e.g. LinkedIn)
    _check_blocked(url)

    # Normalize LinkedIn collection URLs — kept in case LinkedIn is ever removed
    # from BLOCKED_DOMAINS and re-enabled via Playwright.
    url = _normalize_linkedin_url(url)

    try:
        html = fetch_job_html(url)

        # Detect login walls before investing in parsing
        if _detect_login_wall(html, url):
            logger.warning(f"Login wall detected for {url}")
            if "linkedin.com" in url:
                raise ValueError(
                    "LinkedIn requires login to view this job. "
                    "Please use a different job board (Greenhouse, Lever, Indeed, etc.)"
                )
            else:
                raise ValueError(f"The job page at {url} requires login/authentication to view.")

        text = extract_text_from_html(html)

        # If the extracted visual text is very short (e.g. an SPA React/Angular page),
        # we completely bypass Playwright (since headless browsers deadlock the server).
        # We simply pass the raw HTML payload forward so the LLM can extract
        # the structured job details exactly from the embedded JSON state tags.
        if len(text.strip()) < 500:
            logger.warning("Fetched page has very little visual text (Likely a JS-rendered SPA). Passing raw HTML to parser.")
            text = html

        # Ensure text is not empty before returning
        if not text.strip():
             text = html
             text = html

        return html, text
    except ValueError:
        # Re-raise user-friendly errors (login walls, etc.)
        raise
    except Exception as e:
        logger.error(f"Failed to fetch job HTML: {e}")
        raise ValueError(
            f"Could not fetch the job page. Error: {str(e)}. "
            "Please check the URL and try again."
        )
