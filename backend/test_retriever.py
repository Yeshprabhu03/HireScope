from rag.retriever import retrieve_relevant_experiences

results = retrieve_relevant_experiences(
    query="investment banking associate interview process rounds",
    company="Morgan Stanley",
    role="Investment Banking Associate",
    role_category="investment_banking"
)

import json
print(json.dumps(results, indent=2))
