import asyncio
from agents.interview_agent import analyze_interviews

def main():
    print("Fetching Interview Intel for Adobe Compliance Director (0-RAG Simulation)...")
    
    mock_jd = {
        "job_title": "Director, Compliance Investigations",
        "company": "Adobe",
        "jd_text_snippet": "Adobe is seeking a Director, Compliance Investigations to lead internal investigations globally regarding code of conduct violations, fraud, and HR issues. Must have JD and 10+ years experience in corporate investigations."
    }
    
    intel = analyze_interviews(
        job_title="Director, Compliance Investigations",
        company="Adobe",
        parsed_jd=mock_jd,
        company_intel={"description": "Adobe Inc. is a software company known for creative tools."}
    )
    
    # Let's print the entire result
    print("Result:")
    import json
    print(json.dumps(intel, indent=2))

if __name__ == "__main__":
    main()
