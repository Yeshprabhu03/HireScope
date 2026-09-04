"""
Interview Agent: uses RAG + Claude to generate interview intelligence for a company/role.
"""
import json
import logging
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MOCK_INTERVIEW_INTEL = {
    "rounds": [
        "Recruiter Phone Screen (30 min)",
        "Technical Phone Screen - Coding (60 min)",
        "Onsite: 2x Coding Interviews (45 min each)",
        "Onsite: System Design Interview (60 min)",
        "Onsite: Behavioral / Googleyness Interview (45 min)",
    ],
    "technical_questions": [
        "Implement a LRU cache",
        "Find the maximum path sum in a binary tree",
        "Design a URL shortener (system design)",
        "Merge K sorted linked lists",
        "Word break problem (dynamic programming)",
    ],
    "behavioral_questions": [
        "Tell me about a time you had a conflict with a team member",
        "Describe a project where you had to make a decision with incomplete information",
        "How do you handle competing priorities?",
        "Tell me about your most impactful technical contribution",
    ],
    "difficulty": "hard",
    "tips": [
        "Practice on LeetCode - focus on Medium/Hard problems",
        "Review system design fundamentals (CAP theorem, consistent hashing, etc.)",
        "Prepare STAR-format stories for behavioral questions",
        "Communicate your thought process clearly during coding",
        "Ask clarifying questions before coding",
    ],
    "process_overview": "Google's interview process typically consists of 5-7 rounds including phone screens and an onsite loop. Expect algorithmic coding, system design, and behavioral interviews.",
    "source": "RAG (mock data)",
}


async def scrape_on_demand_interviews(company: str, role: str, role_category: str) -> list[str]:
    """
    [DISABLED - Tier 3 fix] Previously generated hallucinated interview experiences and injected
    them into ChromaDB, which polluted all future RAG queries for that company with fake data.
    Now returns empty so the LLM falls back to honest JD-based synthesis.
    Replace this with a real async web scraper (Playwright + Glassdoor) when ready.
    """
    logger.info(f"On-demand scraper disabled for data integrity — skipping injection for {company}/{role}")
    return []

def categorize_role(job_title: str) -> str:
    """Map job titles to strict role categories for targeted retrieval."""
    title_lower = job_title.lower()

    if any(kw in title_lower for kw in ["investment banking", "m&a"]):
        return "investment_banking"
    elif any(kw in title_lower for kw in ["front office", "sales and trading"]):
        return "investment_banking"
    elif any(kw in title_lower for kw in ["product manager", "product management", "pm "]):
        return "product_management"
    elif any(kw in title_lower for kw in ["engineer", "developer", "swe", "software"]):
        return "software_engineering"
    elif any(kw in title_lower for kw in ["data", "analytics", "bi ", "machine learning"]):
        return "data_analytics"
    elif any(kw in title_lower for kw in ["delivery", "program", "project", "scrum", "agile"]):
        return "program_management"
    else:
        return "general"

async def analyze_interviews(
    job_title: str,
    company: str,
    industry: str = "Technology",
    parsed_jd: dict = None,
    company_intel: dict = None,
    jd_text_snippet: Optional[str] = None,
    use_mock: bool = False,
    provider: str = "gemini",
) -> dict:
    """
    Generate an exhaustive study guide and interview intelligence.
    Extract actual questions from RAG, mapped to JD requirements.
    Differentiates between verified reported data and reasoned estimations.
    """
    role = job_title

    if use_mock:
        logger.info(f"Using mock interview intel for '{job_title}' at '{company}'")
        return MOCK_INTERVIEW_INTEL

    try:
        from rag.retriever import retrieve_relevant_experiences
        from utils.llm import llm_generate_json

        class StudyGuideSubsection(BaseModel):
            title: str = Field(description="Title of the subsection")
            importance: Literal["CRITICAL", "HIGH", "MED"] = Field(description="Importance of this topic")
            bullet_points: List[str] = Field(description="Strictly factual, highly technical, verbatim knowledge extraction. No generic advice. Cite the JD strictly.")
            jd_justification: str = Field(description="Explain exactly which line in the JD or company intel justifies this subsection")

        class StudyGuideSection(BaseModel):
            title: str = Field(description="High level category title (e.g., Data Platform & Engineering, Product Strategy)")
            subsections: List[StudyGuideSubsection] = Field(description="Detailed subsections for this category")

        class InterviewGuide(BaseModel):
            rounds: List[str] = Field(description="Chronological sequence of interview rounds")
            technical_questions: List[str] = Field(description="5-7 technical questions/topics, prefixed with 'Reported:' or 'Likely Topic:'")
            behavioral_questions: List[str] = Field(description="4-5 behavioral questions/topics, prefixed with 'Reported:' or 'Likely Topic:'")
            difficulty: Literal["easy", "medium", "hard"] = Field(description="Overall difficulty level")
            tips: List[str] = Field(description="5 actionable preparation tips, strictly factual without generic fluff")
            study_guide: List[StudyGuideSection] = Field(description="Exhaustive study guide divided by technical areas")
            process_overview: str = Field(description="2-3 sentence overview of the process. MUST explicitly mention company-specific details")
            identified_sources: List[str] = Field(description="List of platforms identified from data")
            source: str = Field(description="Synthesis source label")

        # Step 1: Classify Role to enforce strict boundary separation
        role_category = categorize_role(role)
        logger.info(f"Role '{role}' strictly classified as '{role_category}'. Searching RAG.")

        # Three targeted retrieval queries
        tech_results = await retrieve_relevant_experiences(
            query=f"{role} technical interview questions",
            company=company,
            role=role,
            role_category=role_category,
            industry=industry,
            limit=5,
        )
        behavioral_results = await retrieve_relevant_experiences(
            query=f"{role} behavioral interview questions",
            company=company,
            role=role,
            role_category=role_category,
            industry=industry,
            limit=3,
        )
        process_results = await retrieve_relevant_experiences(
            query=f"{role} interview process rounds",
            company=company,
            role=role,
            role_category=role_category,
            industry=industry,
            limit=3,
        )

        def get_doc_data(results: dict) -> list[dict]:
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            if not docs:
                return []

            # Flatten if nested (ChromaDB style)
            if isinstance(docs[0], list):
                docs = docs[0]
            if metas and isinstance(metas[0], list):
                metas = metas[0]

            combined = []
            for i in range(len(docs)):
                combined.append({
                    "text": docs[i],
                    "metadata": metas[i] if i < len(metas) else {}
                })
            return combined[:5]

        tech_data = get_doc_data(tech_results)
        behavioral_data = get_doc_data(behavioral_results)
        process_data = get_doc_data(process_results)

        all_unique_data = tech_data + behavioral_data + process_data

        def is_verified_record(doc: dict) -> bool:
            meta = doc.get("metadata", {})
            meta_company = meta.get("company", "").lower()
            meta_role = meta.get("role", "").lower()

            if company.lower() not in meta_company:
                return False

            # If it's a 'general' role category, we MUST enforce role matching to prevent
            # cross-contamination (e.g., retrieving 'Customer Success' for 'Compliance Director')
            if role_category == "general" and meta_role and meta_role != "unknown":
                target_words = {w for w in role.lower().split() if len(w) > 3}
                meta_words = {w for w in meta_role.split() if len(w) > 3}
                # If there are valid words to compare, they must have at least one overlap
                if target_words and meta_words and not (target_words & meta_words):
                    return False

            return True

        # Count how many actually match the target company and role constraints
        verified_docs = [d for d in all_unique_data if is_verified_record(d)]
        verified_count = len(set([d["text"] for d in verified_docs]))

        # --- PHASE 3: ON DEMAND SCRAPING (DISABLED — see scrape_on_demand_interviews) ---
        # Fake hallucinated injection was a data integrity risk. Skip mid-flight injection.
        # Real scraping can run as a post-analysis BackgroundTask when implemented.
        if verified_count < 3:
            logger.info(f"Only {verified_count} verified records for {company}/{role}. LLM will synthesize from JD context.")
        # --- END PHASE 3 ---

        sources_found = []
        for d in all_unique_data:
            s_meta = d["metadata"].get("sources", [])
            if isinstance(s_meta, str):
                try:
                    s_meta = json.loads(s_meta)
                except:
                    s_meta = [s_meta]
            sources_found.extend(s_meta)

        # Add industry-standard sources if certain categories match
        if role_category == "Product":
            sources_found.append("tryexponent.com")
        if role_category == "Finance":
            sources_found.append("WallStreetOasis")

        sources_found = list(set([s for s in sources_found if s]))
        source_count = len(set([d["text"] for d in all_unique_data]))

        tech_context = "\n\n---\n\n".join([d["text"] for d in tech_data]) if tech_data else "No specific technical data available"
        behavioral_context = "\n\n---\n\n".join([d["text"] for d in behavioral_data]) if behavioral_data else "No specific behavioral data available"
        process_context = "\n\n---\n\n".join([d["text"] for d in process_data]) if process_data else "No specific process data available"

        has_verified_data = verified_count > 0
        confidence_score = 0.9 if verified_count > 2 else 0.7 if verified_count > 0 else 0.4

        jd_summary = json.dumps({k: v for k, v in parsed_jd.items() if k != 'jd_text_snippet'}, indent=2) if parsed_jd else "No specific JD provided."
        jd_snippet = parsed_jd.get('jd_text_snippet', '') if parsed_jd else ""

        jd_context = f"{jd_summary}\n\nRAW JOB DESCRIPTION SNIPPET:\n{jd_snippet}" if jd_snippet else jd_summary

        company_context = json.dumps(company_intel, indent=2) if company_intel else "No specific company context provided."

        prompt = f"""You are an expert Executive Interview Coach and Principal Tech Lead.
We have analyzed {source_count} actual candidate interview experiences for {company} / {industry} from sources including {', '.join(sources_found) if sources_found else 'AI knowledge'}.

Role Category: {role_category}
Target Role: {role}
Company: {company}

--- STRICT ANTI-HALLUCINATION INSTRUCTIONS ---
You are tasked with generating a massive, exhaustive 8-10 section "Complete Study Guide" tailored exactly to this role.
However, you MUST ground every single subsection in reality.
Use the following parsed Job Description and Company Intelligence. If you generate a technical or behavioral requirement that is NOT found in the JD or the company context, YOU FAIL automatically.

Job Description Context:
{jd_context}

Company Intelligence Context:
{company_context}

--- RAG INTERVIEW EXPERIENCES ---
CRITICAL:
1. For any question or round explicitly mentioned in the experiences below, prefix it with "Reported: ".
2. For inferred questions based on JD/patterns, prefix with "Likely Topic: ".
3. STRICT POLICY: DO NOT add generic career advice, fluff, or phrases like "Master the art of...", "Showcase your commitment...", or "Deep dive into...".
4. Extract EXACT questions and topics verbatim from the experiences where possible. IF NO experiences exist or match, you MUST heavily rely on the Job Description Context to logically INFER highly probable, role-specific questions. DO NOT return empty lists for technical or behavioral questions.

Technical Experiences:
{tech_context}

Behavioral Experiences:
{behavioral_context}

Process Experiences:
{process_context}"""

        # gemini-3.6-flash is a "thinking" model — reasoning tokens count against
        # max_output_tokens. 6000 left too little room and the JSON truncated
        # mid-string, so give the largest of our agents generous headroom.
        result = await llm_generate_json(prompt, provider=provider, max_tokens=16000, temperature=0.1, response_schema=InterviewGuide)
        result["confidence_score"] = confidence_score
        result["source_count"] = verified_count
        result["data_warning"] = not has_verified_data
        if "identified_sources" not in result:
            result["identified_sources"] = sources_found

        logger.info(f"Interview intelligence generated for '{role}' at '{company}' (Confidence: {confidence_score})")
        return result

    except Exception as e:
        logger.error(f"Interview analysis failed: {e}", exc_info=True)
        return {
            "rounds": [],
            "technical_questions": [],
            "behavioral_questions": [],
            "difficulty": "unknown",
            "tips": [],
            "process_overview": f"Interview intelligence unavailable: {e}",
            "source": "Error — analysis could not be completed",
            "data_warning": True,
            "confidence_score": 0.0,
            "source_count": 0
        }
