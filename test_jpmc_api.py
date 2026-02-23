import requests

def test_api():
    base_url = "http://localhost:8000/api/jobs"
    
    resp = requests.get(base_url)
    jobs = resp.json()
    jpmc_job_id = None
    for job in jobs:
        if 'oraclecloud' in job.get('job_url', ''):
            jpmc_job_id = job.get('job_id')
            break
            
    if not jpmc_job_id:
        print("JPMC job not found in memory")
        return
        
    print(f"Testing Job ID: {jpmc_job_id}")
    report_resp = requests.get(f"{base_url}/{jpmc_job_id}/report")
    data = report_resp.json()
    
    html = data.get("html_report", "")
    print(f"HTML Length: {len(html)}")
    
    idx = html.find("JPMorgan Chase")
    if idx != -1:
        print("\n--- SNIPPET ---")
        end_idx = html.find("</p>", idx)
        company_text = html[idx:end_idx]
        print(company_text)
        print(f"Length of description chunk: {len(company_text)}")

if __name__ == "__main__":
    test_api()
