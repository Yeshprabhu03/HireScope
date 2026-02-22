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
    industry: str = "",
    use_mock: bool = False,
    provider: str = "gemini",
) -> dict:
    """
    Use RAG to retrieve interview experiences and Gemini to synthesize insights.
    Differentiates between verified reported data and reasoned estimations.
    """
    if use_mock:
        logger.info(f"Using mock interview intel for '{role}' at '{company}'")
        return MOCK_INTERVIEW_INTEL

    try:
        from rag.retriever import retrieve_relevant_experiences
        from utils.llm import llm_generate_json

        # Step 1: Classify Role to generate dynamic queries
        classification_prompt = f"""Classify this job role and generate 3 targeted interview search queries.
Role: {role}
Company: {company}
Industry: {industry}

Return JSON:
{{
  "category": "Tech|Finance|Product|Sales|Other",
  "queries": {{
    "technical": "query for technical skills/questions",
    "behavioral": "query for behavioral/culture fit",
    "process": "query for interview process/rounds"
  }}
}}"""
        classification = llm_generate_json(classification_prompt, provider=provider, temperature=0.0)
        role_category = classification.get("category", "Other")
        queries = classification.get("queries", {
            "technical": f"{role} technical interview questions",
            "behavioral": f"{role} behavioral interview questions",
            "process": f"{role} interview process rounds"
        })

        logger.info(f"Role classified as '{role_category}'. Searching RAG with dynamic queries.")

        # Three targeted retrieval queries
        tech_results = retrieve_relevant_experiences(
            query=queries["technical"],
            company=company,
            role=role,
            industry=industry,
            limit=5,
        )
        behavioral_results = retrieve_relevant_experiences(
            query=queries["behavioral"],
            company=company,
            role=role,
            industry=industry,
            limit=3,
        )
        process_results = retrieve_relevant_experiences(
            query=queries["process"],
            company=company,
            role=role,
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
        
        # Count how many actually match the target company
        verified_docs = [d for d in all_unique_data if company.lower() in d["metadata"].get("company", "").lower()]
        verified_count = len(set([d["text"] for d in verified_docs]))
        
        # Extract sources (Reddit, Exponent, etc.) from metadata
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

        prompt = f"""You are an expert interview intelligence analyst. 
We have analyzed {source_count} actual candidate interview experiences for {company} / {industry} from sources including {', '.join(sources_found) if sources_found else 'AI knowledge'}.

Role Category: {role_category}

CRITICAL INSTRUCTION: 
1. For any question or round explicitly mentioned in the experiences, prefix it with "Reported: ".
2. For any question or round that you are inferring based on role/industry patterns (because evidence is missing), prefix it with "Likely Topic: ".
3. DO NOT hallucinate specific questions if the context is empty; provide high-level topics instead.
4. Adapt the "Technical Questions" specifically to the {role_category} field.

Technical Interview Experiences:
{tech_context}

Behavioral Interview Experiences:
{behavioral_context}

Process/Timeline Experiences:
{process_context}

Return ONLY valid JSON with this structure:
{{
  "rounds": ["<list of interview rounds in order>"],
  "technical_questions": ["<5-7 questions/topics, prefixed with 'Reported:' only if it was in the verified company context, otherwise 'Likely Topic:'>"],
  "behavioral_questions": ["<4-5 questions/topics, prefixed with 'Reported:' only if it was in the verified company context, otherwise 'Likely Topic:'>"],
  "difficulty": "<easy|medium|hard>",
  "tips": ["<5 actionable preparation tips>"],
  "mastery_roadmap": {{
    "technical_syllabus": [
      {{
        "category": "<e.g., AI/ML, Finance Domain, Infra>",
        "topics": [
          {{
            "title": "<short name>",
            "details": "<long descriptive definition of what knowledge is required>"
          }}
        ]
      }}
    ],
    "non_technical_syllabus": [
       {{
        "category": "<e.g., Product Core, Leadership, Strategy>",
        "topics": [
          {{
            "title": "<short name>",
            "details": "<detailed behavioral expectation>"
          }}
        ]
      }}
    ],
    "company_values": [
      {{
        "trait": "<e.g., Proactivity, Inclusivity>",
        "context": "<how it applies to this specific role/company>"
      }}
    ],
    "gap_analysis": {{
      "summary": "<2-3 sentence honest assessment of typical candidate gaps for this role>",
      "priorities": ["<Top 3 specific areas to close before the mirror interview>"]
    }}
  }},
  "process_overview": "<2-3 sentence overview of the interview process>",
  "identified_sources": ["<list of platforms identified from data>"],
  "source": "{f'Based on {verified_count} verified interview experiences' if has_verified_data else 'AI-generated guide based on industry patterns'}"
}}"""

        result = llm_generate_json(prompt, provider=provider, max_tokens=2500, temperature=0.1)
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
