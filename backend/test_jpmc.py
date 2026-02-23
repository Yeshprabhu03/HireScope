from utils.job_fetcher import get_job_content
from agents.jd_parser import parse_job_description

url = "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210692822"
html, text = get_job_content(url, use_mock=False)

print("--- TEXT SNIPPET ---")
print(text[:500])

parsed = parse_job_description(html)
print("\n--- PARSED JD ---")
print(parsed.model_dump())
