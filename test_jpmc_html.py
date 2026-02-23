from database import get_company_snapshot
import json

data = get_company_snapshot("JPMC::Payments- Receivables Online Product Delivery- Senior Associate")
print("Data in DB:", data['data']['description'])

from output.report_gen import generate_html_report

dummy_job_data = {
    "parsed_jd": {"job_title": "Payments- Receivables Online Product Delivery- Senior Associate", "company": "JPMC", "location": "Unknown", "seniority_level": "senior", "required_skills": [], "key_responsibilities": [], "remote_policy": "unknown", "employment_type": "full-time"},
    "html_content": "",
    "job_url": "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210692822"
}

html = generate_html_report(
    job_data=dummy_job_data,
    company_intel=data['data'],
    salary_intel={"min_salary": 0, "max_salary": 0, "median_salary": 0, "confidence": 0, "sources": [], "analysis": "N/A", "currency": "USD"},
    interview_intel={"rounds": [], "questions": [], "technical_focus": [], "cultural_focus": [], "preparation_strategy": "N/A", "source": "N/A"}
)

print("\n--- HTML SNIPPET ---")
idx = html.find("Fortress")
if idx != -1:
    print(html[idx-50:idx+50])
