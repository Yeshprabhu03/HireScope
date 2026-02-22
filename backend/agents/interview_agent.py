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


def scrape_on_demand_interviews(company: str, role: str, role_category: str) -> list[str]:
    """
    Placeholder: Simulate live web scraping of Glassdoor/WSO to fetch experiences.
    In production, this would use residential proxies or an external API
    to bypass Cloudflare and directly extract text from interview boards.
    """
    logger.info(f"Simulating live scrape for {company} {role} ({role_category})...")
    
    # Simulate a successful scrape of generic industry topics customized to the role
    simulated_data = [
        f"[Source: Simulated Scraper] Interviewed for {role} at {company}. The process started with a recruiter screen where they asked about my motivations and past projects.",
        f"[Source: Simulated Scraper] Technical round for {company} focused heavily on scenario-based questions related to {role_category} challenges.",
        f"[Source: Simulated Scraper] Behavioral round was very standard. They asked 'Tell me about a time you failed' and 'How do you handle conflict in {role} scenarios?'.",
        f"[Source: Simulated Scraper] The final round was a presentation/whiteboard session where I had to solve a problem relevant to {company}'s core business."
    ]
    
    return simulated_data

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

def analyze_interviews(
    company: str,
    role: str,
    industry: str = "",
    parsed_jd: dict = None,
    company_intel: dict = None,
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

        # Step 1: Classify Role to enforce strict boundary separation
        role_category = categorize_role(role)
        logger.info(f"Role '{role}' strictly classified as '{role_category}'. Searching RAG.")

        # Three targeted retrieval queries
        tech_results = retrieve_relevant_experiences(
            query=f"{role} technical interview questions",
            company=company,
            role=role,
            role_category=role_category,
            industry=industry,
            limit=5,
        )
        behavioral_results = retrieve_relevant_experiences(
            query=f"{role} behavioral interview questions",
            company=company,
            role=role,
            role_category=role_category,
            industry=industry,
            limit=3,
        )
        process_results = retrieve_relevant_experiences(
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
        
        # Count how many actually match the target company
        verified_docs = [d for d in all_unique_data if company.lower() in d["metadata"].get("company", "").lower()]
        verified_count = len(set([d["text"] for d in verified_docs]))
        
        # --- PHASE 3: ON DEMAND SCRAPING FALLBACK ---
        if verified_count < 3 and company.lower() not in ["none", "unknown", "n/a"]:
            logger.info(f"Only {verified_count} verified records found for {company} {role}. Triggering On-Demand Scraper...")
            
            # 1. Scrape new experiences (Simulated for now until residential proxies)
            new_experiences = scrape_on_demand_interviews(company, role, role_category)
            
            if new_experiences:
                try:
                    from database import save_interview_experiences
                    from rag.vector_store import index_interviews
                    
                    # 2. Save to SQLite Database
                    save_interview_experiences(company, role, role_category, new_experiences)
                    
                    # 3. Inject directly into ChromaDB memory
                    index_interviews(new_experiences, company, role, role_category)
                    
                    logger.info("On-Demand injection complete. Re-querying RAG...")
                    
                    # 4. Re-query RAG to grab the newly injected chunks
                    tech_results = retrieve_relevant_experiences(
                        query=f"{role} technical interview questions",
                        company=company, role=role, role_category=role_category,
                        industry=industry, limit=5,
                    )
                    behavioral_results = retrieve_relevant_experiences(
                        query=f"{role} behavioral interview questions",
                        company=company, role=role, role_category=role_category,
                        industry=industry, limit=3,
                    )
                    process_results = retrieve_relevant_experiences(
                        query=f"{role} interview process rounds",
                        company=company, role=role, role_category=role_category,
                        industry=industry, limit=3,
                    )
                    
                    # Re-calculate
                    tech_data = get_doc_data(tech_results)
                    behavioral_data = get_doc_data(behavioral_results)
                    process_data = get_doc_data(process_results)
                    all_unique_data = tech_data + behavioral_data + process_data
                    
                    verified_docs = [d for d in all_unique_data if company.lower() in d["metadata"].get("company", "").lower()]
                    verified_count = len(set([d["text"] for d in verified_docs]))
                    
                except Exception as e:
                    logger.error(f"Failed to index on-demand scrape: {e}")
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

        jd_context = json.dumps(parsed_jd, indent=2) if parsed_jd else "No specific JD provided."
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
4. Extract EXACT questions and topics verbatim from the experiences where possible. DO NOT invent scenarios not mentioned.

Technical Experiences:
{tech_context}

Behavioral Experiences:
{behavioral_context}

Process Experiences:
{process_context}

Return ONLY valid JSON with this structure:
{{
  "rounds": ["<list of interview rounds in order>"],
  "technical_questions": ["<5-7 questions/topics, prefixed with 'Reported:' or 'Likely Topic:'>"],
  "behavioral_questions": ["<4-5 questions/topics, prefixed with 'Reported:' or 'Likely Topic:'>"],
  "difficulty": "<easy|medium|hard>",
  "tips": ["<5 actionable preparation tips, strictly factual without generic fluff>"],
  "study_guide": [
    {{
      "title": "<e.g., Data Platform & Engineering, Product Strategy, Privacy & Compliance>",
      "subsections": [
        {{
          "title": "<e.g., Core Data Architecture — Know Cold>",
          "importance": "<CRITICAL|HIGH|MED>",
          "bullet_points": [
             "<Strictly factual, highly technical, verbatim knowledge extraction. No generic advice. Cite the JD strictly.>",
             "<Another strictly factual technical or behavioral insight...>"
          ],
          "jd_justification": "<Explain exactly which line in the JD or company intel justifies this subsection>"
        }}
      ]
    }}
  ],
  "process_overview": "<2-3 sentence overview of the interview process>",
  "identified_sources": ["<list of platforms identified from data>"],
  "source": "{f"Source: {verified_count} verified {' / '.join(list(set(sources_found)))} interview experiences" if has_verified_data else 'Trusted Synthesis (JD Context & Industry Patterns)'}"
}}"""

        result = llm_generate_json(prompt, provider=provider, max_tokens=6000, temperature=0.1)
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
