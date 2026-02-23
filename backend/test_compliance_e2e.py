import asyncio
from agents.orchestrator import fetch_interviews_node
import json

def main():
    print("Testing Compliance URL via Orchestrator Node...")
    # Constructing the state that the orchestrator would trigger
    mock_jd = {
        "job_title": "Director, Compliance Investigations",
        "company": "Adobe",
        "jd_text_snippet": "Adobe is seeking a Director, Compliance Investigations to lead internal investigations globally regarding code of conduct violations, fraud, and HR issues."
    }
    company_intel = {
        "description": "Adobe is an American multinational computer software company."
    }
    
    state = {
        "job_id": "test_123",
        "parsed_jd": mock_jd,
        "company_intelligence": company_intel,
        "use_mock": False,
        "provider": "gemini"
    }
    
    result = fetch_interviews_node(state)
    print("Result:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
