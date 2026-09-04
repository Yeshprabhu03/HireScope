import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from utils.llm import llm_generate_json

logger = logging.getLogger(__name__)

class ScoringDimension(BaseModel):
    name: str = Field(description="Name of the dimension (e.g., Tech Stack, WLB, Growth)")
    score: int = Field(description="Score from 0 to 100")
    reasoning: str = Field(description="1-sentence justification for this score")

class CompatibilityScore(BaseModel):
    overall_grade: str = Field(description="Letter grade from A+ to F (e.g., 'A-', 'B', 'F')")
    overall_reasoning: str = Field(description="A concise summary of why this job is a good or bad fit.")
    dimensions: List[ScoringDimension] = Field(description="Breakdown of scores across key career dimensions")

class SkillGap(BaseModel):
    missing_skill: str = Field(description="High-priority skill missing from resume but in JD")
    priority: str = Field(description="Priority: 'high', 'medium', or 'low'")
    recommendation: str = Field(description="Quick advice on how to address this gap (e.g., 'Leverage project X', 'Mention experience with Y')")

class ResumeAITailor(BaseModel):
    ats_keywords_to_add: List[str] = Field(description="Specific technical keywords to inject into the resume for this JD")
    suggested_bullet_points: List[str] = Field(description="2-3 role-specific bullet point rewrites for better JD alignment")
    skill_gaps: List[SkillGap] = Field(description="Analysis of what the user is missing vs what is required")

async def analyze_compatibility(
    parsed_jd: Dict[str, Any],
    company_intel: Dict[str, Any],
    user_context: Optional[str] = None,
    provider: str = "gemini"
) -> Dict[str, Any]:
    """
    Evaluates job compatibility and generates a skill gap analysis using the user's resume/skills context.
    """
    logger.info(f"Analyzing compatibility for {parsed_jd.get('job_title')}")

    # Step 1: Compatibility Scoring
    system_values = "The user values: High technical standards, strong engineering culture, work-life balance transparency, and clear career progression."

    scoring_prompt = f"""
    You are an expert Career Coach and Offer Negotiator. Analyze the following Job Description (JD) and Company Intelligence to calculate a Compatibility Grade (A+ to F).

    USER VALUES:
    {system_values}

    JOB DATA:
    {parsed_jd.get('job_title')} at {parsed_jd.get('company')}
    Industry: {company_intel.get('industry', 'Technology')}
    JD Highlights: {parsed_jd.get('jd_text_snippet', 'N/A')}

    Evaluate deep alignment across dimensions like Tech Stack (is it modern?), Career Growth (tier of company), and Work-Life Balance (inference from culture/reviews).
    """

    compatibility = await llm_generate_json(
        scoring_prompt,
        provider=provider,
        # gemini-3.6-flash is a "thinking" model — reasoning tokens count against
        # max_output_tokens, so a tight budget truncates the JSON before it finishes.
        # Give thinking + output enough combined room.
        max_tokens=6000,
        temperature=0.1,
        response_schema=CompatibilityScore
    )

    # Step 2: Skill Gap Analysis
    if user_context:
        gap_prompt = f"""
        Compare the following Required Skills in the JD against the User's Resume / Skills Background.
        Identify exactly what is missing and how to bridge the gap.

        REQUIRED SKILLS:
        {parsed_jd.get('required_skills', [])}

        USER BACKGROUND (RESUME/SKILLS):
        {user_context}
        """
    else:
        gap_prompt = f"""
        Identify the highest-priority skills and ATS keywords for this JD.
        Since you don't have the user's specific skills yet, generate a generic 'Must-Have' optimization report.

        REQUIRED SKILLS:
        {parsed_jd.get('required_skills', [])}
        """

    gap_analysis = await llm_generate_json(
        gap_prompt,
        provider=provider,
        max_tokens=6000,  # headroom for thinking-model reasoning tokens (see above)
        temperature=0.1,
        response_schema=ResumeAITailor
    )

    return {
        "compatibility": compatibility,
        "gap_analysis": gap_analysis
    }
