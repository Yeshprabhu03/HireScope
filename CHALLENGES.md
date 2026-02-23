# 🛠️ HireScope: Technical Challenges & Solutions

Building a robust, AI-powered job analysis platform involves overcoming significant hurdles in web scraping, data isolation, and AI reasoning. This document captures the major technical challenges faced during the development of HireScope and how they were solved.

---

### 1. The Single Page Application (SPA) "Black Hole"
**Challenge:** 
Modern career portals (Goldman Sachs, Workday, Eightfold) are built as React/Next.js SPAs. When traditional scrapers (like `requests`) fetch the HTML, they receive a nearly empty "Loading..." shell. The actual job data is either fetched via hidden APIs or stored in deeply nested JSON blocks.

**Solution:**
- **Native JSON Extraction:** Instead of relying on slow Headless Chrome (Playwright) which can trigger bot-protection, the parser was upgraded to surgically extract `<script type="application/ld+json">` and `<script id="__NEXT_DATA__">` blocks.
- **Result:** The LLM receives the raw, highly structured React state payload, allowing for perfect parsing of "Machine Learning" at Goldman Sachs even when the visual text is masked.

---

### 2. RAG Cross-Contamination (The "General" Category Bug)
**Challenge:**
When searching for niche roles (e.g., "Director, Compliance"), the Vector Database (ChromaDB) often matched broad roles (e.g., "Customer Success") simply because they shared the `Adobe` company tag and the `general` job category tag. The AI would then present Customer Success questions for a Compliance job.

**Solution:**
- **Strict Word-Overlap Validator:** Implemented the `is_verified_record()` algorithm. It requires at least one significant word (length > 3) to overlap between the target job title and the vector metadata.
- **Direct Forced Restart:** If 0 records pass this strict gate, the system ignores the contaminated vectors and triggers an on-demand web scrape specifically for the niche role.

---

### 3. Asynchronous Model Persistence
**Challenge:**
The frontend allows users to choose between Gemini and Claude (or other providers). However, since analysis is an asynchronous background task, the user's choice was being lost between the initial POST request and the background processing worker.

**Solution:**
- **State Object Enrichment:** The `JobAnalysisState` was updated to explicitly carry the `provider` string through every "Node" in the LangGraph orchestrator. This ensures the Salary Agent and Interview Agent always use the specific LLM requested by the user.

---

### 4. Fragmented Salary Intelligence
**Challenge:**
Job listings often mention specific salary ranges (e.g., "$150k - $220k"), but our primary data source was the Department of Labor (DOL) H1B database, which can be 12-18 months out of date or missing for niche roles.

**Solution:**
- **Continuous Learning DB:** Created a dual-source intelligence system. The system now extracts explicit JD salary strings, normalizes them into integers, and saves them to a local SQLite `salary_observations` table. 
- **Learning Logic:** Once 5 local observations exist for a role, the system prioritizes its own "Learned Dataset" over the H1B baseline.

---

### 5. Bot Protection & Header Mimicry
**Challenge:**
Websites like LinkedIn and Greenhouse aggressively block automated traffic with 403 Forbidden errors if they detect standard Python headers.

**Solution:**
- **Advanced Header Rotation:** The `job_fetcher.py` mimics a modern Chrome browser on MacOS, including the removal of Brotli (`br`) encoding which several Python libraries fail to decode properly.
- **Model Bypasses:** Relaxed LinkedIn auth-wall detection to permit public "Guest" views, enabling the AI to read titles like "Company hiring Role" without an active login.

---

Built with ❤️ by [@Yeshprabhu03](https://github.com/Yeshprabhu03)
