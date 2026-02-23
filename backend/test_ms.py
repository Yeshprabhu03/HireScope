import json
from agents.interview_agent import analyze_interviews

# Mock input for Morgan Stanley
intel = analyze_interviews(
    company="Morgan Stanley",
    role="Investment Banking Summer Associate Program",
    industry="Finance",
    parsed_jd={"role": "Investment Banking Associate"}
)

print(json.dumps(intel, indent=2))
