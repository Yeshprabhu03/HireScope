import asyncio
from agents.jd_parser import parse_job_description
from data_sources.company_intel import fetch_company_intel

html_content = """
<html>
<title>Senior Manager of Customer Success - Adobe</title>
<body>
<p>We are hiring a Senior Manager of Customer Success to join our Digital Experience Cloud team. To achieve the significant opportunity ahead, Adobe Customer Success needs to own the post-sales customer experience, driving adoption and value for our customers. In this role, you will serve as an industry-specialized Customer Success leader passionate about guiding your team to achieve their customers' goals for personalization at scale. We hire dynamic, hard-working, and creative individuals, adept at storytelling who thrive in fast-paced environments.</p>
</body>
</html>
"""

def main():
    print("Parsing JD...")
    parsed = parse_job_description(html_content)
    parsed_demo = parsed.model_dump()
    print("Extracted Business Unit:", parsed_demo.get("business_unit"))
    
    print("Fetching Company Intel...")
    intel = fetch_company_intel("Adobe", "Senior Manager of Customer Success", parsed_jd=parsed_demo)
    print("Business Unit Overview:", intel.get("business_unit_overview"))

if __name__ == "__main__":
    main()
