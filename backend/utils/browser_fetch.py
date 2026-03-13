import asyncio
import sys
from playwright.async_api import async_playwright

async def fetch_rendered_text(url: str):
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        try:
            page = await browser.new_page()
            
            # 1. Navigate
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                sys.stderr.write(f"Warning: Page load timed out for {url}: {e}\n")

            # 2. Extract Title early
            title = await page.title()
            main_content = ""

            # 3. Targeted extraction for Careers sites (Radical Pruning)
            if any(domain in url for domain in ["google.com", "microsoft.com", "oraclecloud.com"]):
                try:
                    # Wait for markers to appear if they are likely to be there
                    # This handles heavy SPAs like Eightfold (Microsoft)
                    try:
                        await page.wait_for_function("""() => {
                            const markers = ['Minimum qualifications', 'About the job', 'Responsibilities', 'Required Qualifications', 'Job description', 'Qualifications', 'YOUR IMPACT', 'OUR IMPACT', 'ABOUT GOLDMAN SACHS'];
                            return markers.some(m => document.body.innerText.includes(m));
                        }""", timeout=15000)
                    except:
                        sys.stderr.write(f"Warning: Timed out waiting for job markers on {url}\n")
                        
                    # Radical Pruning: Always remove common noise tags first
                    await page.evaluate("""() => {
                        const noise = document.querySelectorAll('script, style, noscript, iframe, nav, footer, header, .gc-sidebar, .gc-search-results, [aria-label="Filter"], .ms-search-list');
                        noise.forEach(e => e.remove());
                        
                        const markers = [
                        'Minimum qualifications', 'About the job', 'Responsibilities', 
                        'Required Qualifications', 'Job description', 'Qualifications', 
                        'YOUR IMPACT', 'OUR IMPACT', 'ABOUT GOLDMAN SACHS',
                        'NYSE', 'ICE Data Services', 'Intercontinental Exchange'
                    ];
                        let mainContainer = document.querySelector('main, [role="main"], [aria-label="Job details"], #job-details, .job-description, [data-testid="job-details"]');
                        
                        if (!mainContainer) {
                            // Find the largest div that contains at least one marker
                            const divs = Array.from(document.querySelectorAll('div, section, article'))
                                             .filter(e => markers.some(m => e.innerText.includes(m)) && e.innerText.length > 500);
                            if (divs.length > 0) {
                                divs.sort((a, b) => b.innerText.length - a.innerText.length);
                                mainContainer = divs[0];
                            }
                        }
                        
                        // Only prune if we found something substantial (~500 chars)
                        if (mainContainer && mainContainer.innerText.length > 500) {
                            const content = mainContainer.innerHTML;
                            document.body.innerHTML = content;
                        }
                    }""")
                    
                    # Small wait for DOM to settle
                    await asyncio.sleep(0.5)
                except Exception as e:
                    sys.stderr.write(f"Radical pruning failed for {url}: {e}\n")

            # 5. Output FULL HTML
            print(await page.content())

        except Exception as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(fetch_rendered_text(sys.argv[1]))
    else:
        sys.exit(1)
