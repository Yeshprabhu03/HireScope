import asyncio
from utils.job_fetcher import fetch_job_html

async def run():
    html = await fetch_job_html("https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210715750/?utm_medium=jobshare&utm_source=External+Job+Share")
    print(html[:2000] if html else "FAIL")

asyncio.run(run())
