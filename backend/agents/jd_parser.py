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
def parse_job_description(html: str, use_mock: bool = False) -> ParsedJD:
    """
    Parse a job description HTML using Claude to extract structured data.
    Falls back to mock data if use_mock=True or API call fails.
    """
    if use_mock:
        logger.info("Using mock parsed JD data")
        return MOCK_PARSED_JD

    try:
        from anthropic import Anthropic
        from config import settings

        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        schema = ParsedJD.model_json_schema()
        prompt = f"""Extract structured data from this job posting HTML.
Return ONLY valid JSON that matches this exact schema (no markdown, no code blocks):
{json.dumps(schema, indent=2)}

Important rules:
- If a field is not found, use the default value from the schema
- seniority_level must be one of: intern, junior, mid, senior, staff, principal, director
- remote_policy must be one of: remote, hybrid, onsite, unknown
- required_skills should include both technical skills and important soft skills
- key_responsibilities should have at most 8 items, each concise

<html>
{html[:15000]}
</html>"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        raw_text = response.content[0].text.strip()
        # Strip markdown code blocks if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed_data = json.loads(raw_text)
        result = ParsedJD(**parsed_data)
        logger.info(f"Parsed JD: {result.job_title} at {result.company}")
        return result

    except Exception as e:
        logger.error(f"JD parsing failed: {e}", exc_info=True)
        raise
