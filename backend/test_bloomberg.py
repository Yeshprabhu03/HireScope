import asyncio
from data_sources.company_intel import fetch_company_intel

def main():
    print("Testing Bloomberg CEO Extraction...")
    mock_jd = {
        "job_title": "Software Engineer",
        "company": "Bloomberg",
    }
    
    intel = fetch_company_intel(company="Bloomberg", role="Software Engineer", parsed_jd=mock_jd)
    
    import json
    print(json.dumps(intel, indent=2))

if __name__ == "__main__":
    main()
