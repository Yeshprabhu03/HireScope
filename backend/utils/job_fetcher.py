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
    "linkedin.com",
]

# Domains that actively block all automated access (even headless browsers).
# Skip the real fetch entirely and go straight to mock data immediately.
ALWAYS_MOCK_DOMAINS = [
    "linkedin.com",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
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


def _always_mock(url: str) -> bool:
    """Return True if this domain always blocks scrapers (use mock immediately)."""
    return any(domain in url for domain in ALWAYS_MOCK_DOMAINS)


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
        return True

    indicator_count = sum(1 for ind in login_indicators if ind.lower() in text.lower())
    if indicator_count >= 2:
        return True

    return False


def fetch_job_html_with_playwright(url: str) -> str:
    """
    Fetch HTML from a JS-rendered page using Playwright (headless Chromium).
    Uses domcontentloaded (not networkidle) to avoid hanging on sites with
    continuous background requests. Hard timeout of 15 seconds.
    """
    logger.info(f"Using Playwright to fetch JS-rendered page: {url}")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=HEADERS["User-Agent"],
                locale="en-US",
            )
            page = context.new_page()
            # Use domcontentloaded instead of networkidle — networkidle
            # hangs on sites like LinkedIn that continuously load resources
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Brief wait to allow JS components to render
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            logger.info(f"Playwright fetched {len(html)} chars from {url}")
            return html
    except Exception as e:
        logger.error(f"Playwright fetch failed for {url}: {e}")
        raise


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
def fetch_job_html(url: str) -> str:
    """
    Fetch HTML content from a job posting URL.
    Uses Playwright for JS-rendered sites, requests for static pages.
    Retries up to 2 times with exponential backoff.
    """
    logger.info(f"Fetching job HTML from: {url}")
    if _needs_browser(url):
        return fetch_job_html_with_playwright(url)

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        logger.info(f"Successfully fetched HTML ({len(response.text)} chars)")
        return response.text
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error fetching {url}: {e}")
        raise
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"Connection error fetching {url}: {e}")
        raise
    except requests.exceptions.Timeout as e:
        logger.warning(f"Timeout fetching {url}: {e}")
        raise


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
    Falls back to mock data if use_mock=True or if the domain always blocks scrapers.
    Raises ValueError with a user-friendly message if fetch fails for other sites.
    """
    if use_mock or _always_mock(url):
        if _always_mock(url):
            logger.warning(
                f"Domain blocks automated access ({url}). Using mock data. "
                "Tip: use a job board that allows direct access (Greenhouse, Lever, Indeed, etc.)"
            )
        else:
            logger.info("Using mock job HTML data")
        html = MOCK_JOB_HTML
        return html, extract_text_from_html(html)

    # Normalize LinkedIn collection URLs to direct job URLs
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

        # If we got almost no text, try Playwright as a fallback
        if len(text.strip()) < 100:
            logger.warning("Fetched page has very little text — may be bot-blocked. Trying Playwright fallback.")
            html = fetch_job_html_with_playwright(url)

            if _detect_login_wall(html, url):
                raise ValueError(f"The job page at {url} requires login/authentication to view.")

            text = extract_text_from_html(html)

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
