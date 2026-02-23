import requests

def fetch_wiki(name):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{name}"
    r = requests.get(url, headers={"User-Agent": "HireScope/1.0"})
    if r.status_code == 200:
        data = r.json()
        if data.get("type") == "disambiguation":
            print(f"[{name}] is a disambiguation page!")
            return fetch_wiki(f"{name} (company)")
        return data.get("extract", "")
    return None

print(fetch_wiki("Amazon")[:100])
print(fetch_wiki("Bloomberg")[:100])
