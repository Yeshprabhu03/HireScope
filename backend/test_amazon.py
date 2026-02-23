import json
from agents.interview_agent import analyze_interviews

# Mock input for Amazon
intel = analyze_interviews(
    company="Amazon",
    role="Sr. Business Development Manager, CTV",
    industry="Tech",
    parsed_jd={"role": "Sr. Business Development Manager"}
)

print(json.dumps(intel, indent=2))
