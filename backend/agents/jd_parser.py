"""
JD Parser: uses Claude to extract structured data from job posting HTML.
"""
import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ParsedJD(BaseModel):
    job_title: str = Field(default="Unknown", description="Job title/position name")
    company: str = Field(default="Unknown", description="Company name")
    location: str = Field(default="Unknown", description="Job location (city, state, remote)")
    business_unit: str = Field(default="N/A", description="Specific business unit, product team, or department mentioned in the JD (e.g., 'Digital Experience Cloud', 'AWS', 'Investment Banking'). Use 'N/A' if truly not specified.")
    seniority_level: str = Field(
        default="mid",
        description="Seniority level: intern, junior, mid, senior, staff, principal, director",
    )
    required_skills: list[str] = Field(
        default_factory=list, description="List of required technical and soft skills"
    )
    years_experience_min: Optional[int] = Field(
        default=None, description="Minimum years of experience required"
    )
    years_experience_max: Optional[int] = Field(
        default=None, description="Maximum years of experience required"
    )
    salary_mentioned: Optional[str] = Field(
        default=None, description="Salary or compensation if mentioned in the JD"
    )
    remote_policy: str = Field(
        default="unknown",
        description="Remote work policy: remote, hybrid, onsite, unknown",
    )
    key_responsibilities: list[str] = Field(
        default_factory=list, description="Key job responsibilities (max 8)"
    )
    education_required: Optional[str] = Field(
        default=None, description="Required education level"
    )
    employment_type: str = Field(
        default="full-time",
        description="Employment type: full-time, part-time, contract, internship",
    )


MOCK_PARSED_JD = ParsedJD(
    job_title="Senior Software Engineer",
    company="Google",
    location="Mountain View, CA",
    business_unit="Google Cloud Platform",
    seniority_level="senior",
    required_skills=["Python", "Java", "Go", "Distributed Systems", "Cloud Computing"],
    years_experience_min=5,
    years_experience_max=None,
    salary_mentioned="$180,000 - $250,000 per year",
    remote_policy="hybrid",
    key_responsibilities=[
        "Design, develop, and maintain scalable software systems",
        "Lead technical discussions and code reviews",
        "Collaborate with cross-functional teams",
        "Mentor junior engineers",
    ],
    education_required="BS/MS in Computer Science",
    employment_type="full-time",
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def parse_job_description(html: str, use_mock: bool = False, provider: str = "gemini") -> ParsedJD:
    """
    Parse a job description HTML using Claude to extract structured data.
    Falls back to mock data if use_mock=True or API call fails.
    """
    if use_mock:
        logger.info("Using mock parsed JD data")
        return MOCK_PARSED_JD

    try:
        from utils.llm import llm_generate_json
        from bs4 import BeautifulSoup
        
        schema = ParsedJD.model_json_schema()
        
        # Optimize token usage by stripping HTML tags
        soup = BeautifulSoup(html, "html.parser")
        
        # Save script tags in case the page is a SPA with JSON variables
        # Also specifically look for structured schema.org data (application/ld+json)
        scripts = soup.find_all('script')
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        json_ld_text = "\n".join([s.get_text() for s in json_ld_scripts if s.get_text()])
        
        # Remove script and style elements for clean text extraction
        for script in soup(["script", "style", "noscript"]):
            script.decompose()
            
            
        # Extract meta tags explicitly and label them so the LLM knows their significance
        extracted_meta = []
        if soup.title and soup.title.string:
            extracted_meta.append(f"Page Title: {soup.title.string}")
            
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            extracted_meta.append(f"Job Title Metadata (og:title): {og_title.get('content')}")
            
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            extracted_meta.append(f"Job Description Metadata (og:description): {og_desc.get('content')}")
            
        meta_text = "\n".join(extracted_meta)
            
        # Get text content with minimal markdown-like structure
        clean_text = soup.get_text(separator="\n", strip=True)
        
        # Prepend the meta tag content to give clear hints about Title and Description
        if meta_text:
            clean_text = f"--- CRITICAL METADATA ---\n{meta_text}\n--- PAGE CONTENT ---\n{clean_text}"
            
        # Always append Structured Schema JSON if it exists!
        if json_ld_text:
            clean_text = f"{clean_text}\n\n--- STRUCTURED JOB DATA ---\n{json_ld_text}"
            
        # If the extracted visual text is very short (e.g. Oracle Cloud JS page), 
        # append ALL script contents so the LLM can parse the ugly JSON state data.
        if len(clean_text) < 500:
            script_text = "\n".join([s.get_text() for s in scripts if s.get_text() and s not in json_ld_scripts])
            clean_text += "\n\n--- JSON/JAVASCRIPT APP STATE ---\n\n" + script_text
            
        # Truncate to a reasonable length (e.g., 30k chars is plenty for Gemini's context)
        # but huge savings compared to raw HTML with scripts
        clean_text = clean_text[:30000]
        
        # Escape triple quotes to prevent breaking the f-string
        clean_text = clean_text.replace('"""', "'''")

        prompt = f"""Extract structured data from this job posting text or JSON data.
Return ONLY valid JSON that matches this exact schema (no markdown, no code blocks):
{json.dumps(schema, indent=2)}

Important rules:
- If a field is not found, use the default value from the schema
- seniority_level must be one of: intern, junior, mid, senior, staff, principal, director
- remote_policy must be one of: remote, hybrid, onsite, unknown
- required_skills should include both technical skills and important soft skills
- key_responsibilities should have at most 8 items, each concise

Job Posting Text:
{clean_text}"""

        parsed_data = llm_generate_json(prompt, provider=provider, max_tokens=2000, temperature=0.0)
        result = ParsedJD(**parsed_data)
        logger.info(f"Parsed JD: {result.job_title} at {result.company}")
        return result

    except Exception as e:
        logger.error(f"JD parsing failed: {e}", exc_info=True)
        raise
