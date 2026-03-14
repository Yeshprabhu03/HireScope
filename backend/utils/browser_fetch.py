import asyncio
import sys
import os
from playwright.async_api import async_playwright

async def fetch_rendered_text(url: str):
    async with async_playwright() as p:
        # Switch to Webkit for better stability and stealth on macOS
        browser = await p.webkit.launch(
            headless=True
        )
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            # For Webkit, we rely on natural Safari fingerprints.
            sys.stderr.write(f"Stealth browser navigating to: {url}\n")

            # 1. Navigate with more generous timeout
            try:
                await page.goto(url, wait_until="load", timeout=30000)
            except Exception as e:
                sys.stderr.write(f"Warning: Page load issue for {url}: {e}\n")

            # 2. Extract Title early
            title = await page.title()
            sys.stderr.write(f"Page Title: {title}\n")

            # 3. Targeted extraction for Careers sites (Radical Pruning)
            if any(domain in url for domain in ["google.com", "microsoft.com", "oraclecloud.com", "linkedin.com"]):
                try:
                    # Radical Pruning: Always remove common noise tags first
                    await page.evaluate("""() => {
                        const markers = [
                            'Minimum qualifications', 'About the job', 'Responsibilities',
                            'Required Qualifications', 'Job description', 'Qualifications',
                            'YOUR IMPACT', 'OUR IMPACT', 'ABOUT GOLDMAN SACHS',
                            'Associate', 'Manager', 'Director'
                        ];
                        const jsonLdScripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));

                        const noise = document.querySelectorAll('script:not([type="application/ld+json"]), style, noscript, iframe, nav, footer, header, .gc-sidebar, .gc-search-results, [aria-label="Filter"], .ms-search-list');
                        noise.forEach(e => e.remove());

                        let mainContainer = document.querySelector('main, [role="main"], [aria-label="Job details"], #job-details, .job-description, [data-testid="job-details"], .jobs-description');

                        if (!mainContainer) {
                            const divs = Array.from(document.querySelectorAll('div, section, article'))
                                             .filter(e => e.innerText.length > 300);
                            if (divs.length > 0) {
                                divs.sort((a, b) => b.innerText.length - a.innerText.length);
                                mainContainer = divs[0];
                            }
                        }

                        if (mainContainer && mainContainer.innerText.length > 300) {
                            document.body.innerHTML = '';
                            jsonLdScripts.forEach(s => document.body.appendChild(s));
                            document.body.appendChild(mainContainer);
                        }
                    }""")

                    await asyncio.sleep(1)
                except Exception as e:
                    sys.stderr.write(f"Pruning failed: {e}\n")

            # 5. Output FULL HTML
            # We print THIS to stdout for the subprocess to capture
            print(await page.content())

        except Exception as e:
            sys.stderr.write(f"Error fetching {url}: {e}\n")
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(fetch_rendered_text(sys.argv[1]))
    else:
        sys.exit(1)
