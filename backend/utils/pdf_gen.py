import asyncio
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

async def generate_pdf_from_html(html_content: str) -> bytes:
    """
    Converts HTML content to a PDF buffer using Playwright.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Set content and wait for it to be rendered
        await page.set_content(html_content, wait_until="networkidle")
        
        # Generate PDF with standard options
        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "20px", "right": "20px", "bottom": "20px", "left": "20px"},
            prefer_css_page_size=True
        )
        
        await browser.close()
        return pdf_bytes

if __name__ == "__main__":
    # Quick test
    async def test():
        test_html = "<html><body><h1>Test Report</h1><p>HireScope PDF Generation Test.</p></body></html>"
        pdf = await generate_pdf_from_html(test_html)
        print(f"Generated PDF size: {len(pdf)} bytes")
        with open("test.pdf", "wb") as f:
            f.write(pdf)
            
    asyncio.run(test())
