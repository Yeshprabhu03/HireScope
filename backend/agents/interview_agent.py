"""
Interview Agent: uses RAG + Claude to generate interview intelligence for a company/role.
"""
import json
import logging
from typing import Optional

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


def analyze_interviews(
    company: str,
    role: str,
    use_mock: bool = False,
) -> dict:
    """
    Use RAG to retrieve interview experiences and Claude to synthesize insights.
    """
    if use_mock:
        logger.info(f"Using mock interview intel for '{role}' at '{company}'")
        return MOCK_INTERVIEW_INTEL

    try:
        from rag.retriever import retrieve_relevant_experiences

        # Three targeted retrieval queries
        tech_results = retrieve_relevant_experiences(
            query="technical interview questions coding algorithms data structures",
            company=company,
            role=role,
            limit=5,
        )
        behavioral_results = retrieve_relevant_experiences(
            query="behavioral interview questions leadership conflict teamwork",
            company=company,
            role=role,
            limit=3,
        )
        process_results = retrieve_relevant_experiences(
            query="interview process rounds phone screen onsite timeline",
            company=company,
            role=role,
            limit=3,
        )

        def flatten_docs(results: dict) -> str:
            docs = results.get("documents", [])
            if docs and isinstance(docs[0], list):
                docs = [d for sublist in docs for d in sublist]
            return "\n\n---\n\n".join(docs[:5]) if docs else "No data available"

        tech_context = flatten_docs(tech_results)
        behavioral_context = flatten_docs(behavioral_results)
        process_context = flatten_docs(process_results)

        has_real_data = (
            len(tech_results.get("documents", [])) > 0
            or len(behavioral_results.get("documents", [])) > 0
        )

        from utils.llm import llm_generate_json

        prompt = f"""You are an interview intelligence analyst. Based on the interview experiences below,
synthesize key insights for a candidate interviewing for {role} at {company}.

Technical Interview Experiences:
{tech_context}

Behavioral Interview Experiences:
{behavioral_context}

Process/Timeline Experiences:
{process_context}

Return ONLY valid JSON with this structure:
{{
  "rounds": ["<list of interview rounds in order>"],
  "technical_questions": ["<5-7 specific technical questions or topics likely to be asked>"],
  "behavioral_questions": ["<4-5 behavioral questions likely to be asked>"],
  "difficulty": "<easy|medium|hard>",
  "tips": ["<5 actionable preparation tips>"],
  "process_overview": "<2-3 sentence overview of the interview process>",
  "source": "RAG-powered analysis"
}}"""

        result = llm_generate_json(prompt, max_tokens=1200, temperature=0.1)

        if not has_real_data:
            result["source"] = (
                "AI-generated guide (no verified interview data for this company). "
                "Prepare using industry-standard patterns for this role level."
            )
            result["data_warning"] = True

        logger.info(f"Interview intelligence generated for '{role}' at '{company}'")
        return result

    except Exception as e:
        logger.error(f"Interview analysis failed: {e}", exc_info=True)
        # Return a minimal honest response — no mock data
        return {
            "rounds": [],
            "technical_questions": [],
            "behavioral_questions": [],
            "difficulty": "unknown",
            "tips": [],
            "process_overview": f"Interview intelligence unavailable: {e}",
            "source": "Error — analysis could not be completed",
            "data_warning": True,
        }
