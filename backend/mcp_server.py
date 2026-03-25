import asyncio
import logging
import uuid
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirescope-mcp")

# Initialize FastMCP - the "brain" will be the name of the server in Claude/IDEs
mcp = FastMCP("HireScope")

@mcp.tool()
async def get_glassdoor_rating(company_name: str) -> str:
    """
    Find real rating and insights for a company on Glassdoor.
    Returns rating, review count, and key pros/cons.
    """
    from utils.glassdoor import get_glassdoor_data

    logger.info(f"MCP Request: Glassdoor rating for '{company_name}'")
    data = await get_glassdoor_data(company_name)

    if data.get("rating") == 0 or data.get("rating") == "N/A":
        return f"Could not find reliable Glassdoor data for '{company_name}'."

    summary = f"""# Glassdoor Insights: {company_name}
- **Rating:** {data.get('rating')}/5.0
- **Reviews:** {data.get('review_count')}
- **Pros:** {', '.join(data.get('pros', []))}
- **Cons:** {', '.join(data.get('cons', []))}
- **URL:** {data.get('url')}
"""
    return summary

@mcp.tool()
async def analyze_job(job_url: str, provider: str = "gemini") -> str:
    """
    Analyze a job posting from a URL using HireScope's intelligence pipeline.
    Returns a structured intelligence report including JD analysis, company financials, and salary data.
    """
    from agents.orchestrator import run_job_analysis

    job_id = f"mcp-{uuid.uuid4().hex[:8]}"
    logger.info(f"MCP Request: Analyzing {job_url} with id={job_id}")

    # We pass an empty dict for jobs tracking since we don't have the FastAPI in-memory store here
    # but run_job_analysis is robust to this.
    result = await run_job_analysis(job_id=job_id, job_url=job_url, provider=provider, jobs={})

    if result.get("status") == "failed":
        return f"Analysis Failed: {result.get('error', 'Unknown error')}"

    # Format a concise summary for the LLM
    jd = result.get("parsed_jd", {})
    comp = result.get("company_intelligence", {})
    sal = result.get("salary_intelligence", {})

    summary = f"""
# Job Intelligence Report: {jd.get('job_title', 'Unknown')} at {jd.get('company', 'Unknown')}

## 📋 Role Overview
- **Location:** {jd.get('location', 'N/A')}
- **Seniority:** {jd.get('seniority_level', 'N/A')}
- **Skills:** {', '.join(jd.get('required_skills', []))}

## 🏢 Company Insights
- **Industry:** {comp.get('industry', 'N/A')}
- **Mission:** {comp.get('mission', 'N/A')}
- **Financials:** {comp.get('market_cap', 'N/A')} Market Cap

## 💰 Salary Intelligence
- **Estimated Range:** {sal.get('estimated_range', 'N/A')}
- **Confidence:** {int(sal.get('confidence_score', 0) * 100)}%

## 🎯 Interview Deep-Dive (Top 3 Questions)
"""
    interviews = result.get("interview_intelligence", {}).get("questions", [])
    for q in interviews[:3]:
        summary += f"- {q.get('question', q)}\n"

    return summary

@mcp.tool()
async def search_vault(query: str, limit: int = 5) -> str:
    """
    Search your personal HireScope "My Jobs Vault" for previously analyzed job reports.
    """
    from database import engine, JobPosting
    from sqlmodel import select
    from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

    logger.info(f"MCP Request: Searching vault for '{query}'")

    async with SQLModelAsyncSession(engine) as session:
        # Simple search across title and company
        statement = select(JobPosting).where(
            (JobPosting.job_title.like(f"%{query}%")) |
            (JobPosting.company.like(f"%{query}%"))
        ).limit(limit)

        results = await session.execute(statement)
        jobs = results.scalars().all()

        if not jobs:
            return f"No reports found in the vault matching '{query}'."

        output = "# Found Reports in Vault\n"
        for job in jobs:
            output += f"- [{job.job_title} at {job.company}] ({job.job_url}) - Analyzed: {job.scraped_at.strftime('%Y-%m-%d')}\n"

        return output

if __name__ == "__main__":
    mcp.run()
