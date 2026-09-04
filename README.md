# 🔍 HireScope — Job Intelligence in Seconds

HireScope is an AI-powered job analysis platform that transforms any job posting URL into a comprehensive intelligence report. Paste a link, get insights on salary, company culture, interview prep, and more.

![HireScope](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![React](https://img.shields.io/badge/React-18-61DAFB)
![AI](https://img.shields.io/badge/AI-OpenAI%20GPT--4o%20%7C%20Gemini%20%7C%20Claude-412991)

## ✨ Features

- **🌐 Robust Job Page Scraping** — Fetches and parses job postings from any URL natively into structured JSON. Includes dynamic extraction strategies with **Radical DOM Pruning** for Workday, Eightfold, and Next.js SPAs (Goldman Sachs, Oracle Cloud) to bypass bot protection boundaries.
- **📄 Native PDF Processing** — Bypass corporate firewalls and login walls by uploading a raw PDF job description directly for full-scale AI analysis.
- **📋 JD Parsing & Team Intelligence** — AI-powered extraction of job details, including a specialized **Sub-Team Deep Dive** that identifies specific internal groups (e.g., "Ayco") for hyper-specific research.
- **🏢 Company Intelligence** — Real-time Market Cap integration via Yahoo Finance (`yfinance`) + robust Wikipedia research with **Iterative Suffix Stripping** for complex legal names and **Relevance-Aware Redirect Handling** to prevent subsidiary data loss.
- **💰 Salary Intelligence** — Triangulated salary estimates from DOL H1B data, JD mentions, and AI market analysis.
- **🎭 Intelligent URL Routing** — Automatically detects and routes problematic job boards (LinkedIn, ICE, Microsoft) through a robust **Playwright-driven browser fetcher** with a custom User-Agent to bypass bot detection.
- **🎯 High-Fidelity Mastery Roadmap** — Role-aware, dynamic RAG-powered interview intelligence featuring hierarchical technical/non-technical mastery categories. Includes multi-platform data vetting (Reddit, WallStreetOasis, Exponent).
- **📊 Professional HTML Report** — Full-width, clean UI report with Mermaid-driven corporate structure visualization and confidence indicators.
- **⏱️ Real-Time Progress** — Live progress bar powered by LangGraph streaming, showing each analysis node as it completes.
- **🔌 MCP Integration** — Includes a fully compliant **Model Context Protocol (MCP)** server, allowing AI clients like Claude Desktop and Cursor to natively trigger job analysis and search your historical vault. See `mcp_guide.md` for setup.

## 🧠 Continuous Learning Architecture (Updated March 13, 2026)

HireScope recently evolved from a stateless script into an intelligent, stateful system that learns and improves over time via a local SQLite database and dynamic ChromaDB (Vector Search) indexing.

- **Phase 1 (Agentic Orchestration)** — Migrated from sequential scripts to **LangGraph**, enabling conditional routing, automated browser-based error recovery, and robust streaming state updates.
- **Phase 2 (Data Caching)** — Eliminates redundant external API calls by caching parsed job descriptions and Wikipedia snapshots.
- **Phase 3 (Salary Intelligence)** — Automatically extracts explicit JD salary strings to build a proprietary baseline database, prioritizing "Learned Data" over DOL H1B data.
- **Phase 4 (Dynamic RAG Indexing)** — Intercepts sparse RAG searches. If there are `< 3` interview experiences for a company, the system live-scrapes the web and injects the new vectors directly into the ChromaDB memory mid-flight.
- **Phase 5 (Testing & Benchmarking)** — Parameter-driven evaluation suite orchestrates deterministic testing across Glassdoor tools, Company Intel gathering, and agent reliability.

## 🏗️ Architecture

```
HireScope/
├── backend/                  # FastAPI + Python
│   ├── main.py               # API server & job orchestration
│   ├── mcp_server.py         # Model Context Protocol (MCP) Server for LLM clients
│   ├── database.py           # Universal SQLite/PostgreSQL caching & storage
│   ├── config.py             # Environment configuration
│   ├── agents/
│   │   ├── orchestrator.py   # LangGraph pipeline (6-step analysis)
│   │   ├── jd_parser.py      # Job description parser (Gemini)
│   │   ├── salary_agent.py   # Salary intelligence agent
│   │   └── interview_agent.py# Interview prep agent
│   ├── data_sources/
│   │   ├── company_intel.py  # Company data (Wikipedia + Gemini)
│   │   └── dol_h1b.py        # DOL H1B salary data
│   ├── utils/
│   │   ├── llm.py            # Centralized multi-provider LLM helper (OpenAI/Gemini/Claude)
│   │   ├── job_fetcher.py    # URL scraping (requests + Playwright)
│   │   ├── browser_fetch.py  # Advanced stealth Playwright fetcher
│   │   └── glassdoor.py      # Glassdoor company reviews API
│   ├── rag/                  # RAG for interview experiences
│   └── output/
│       └── report_gen.py     # HTML report generator
├── frontend/                 # React + TypeScript + Vite
│   └── src/
│       └── components/
│           ├── Dashboard.tsx  # Job list with progress tracking
│           └── ReportViewer.tsx # Report display & editing
├── tests/                    # Parameterized evals & deterministic test suite
├── chroma_db/                # Local ChromaDB vector storage for RAG
├── data/                     # Local H1B CSVs & interview corpus JSONs
├── mcp_guide.md              # Documentation for Claude Desktop integration
└── .env                      # API keys (not committed)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- An LLM API key — **OpenAI is the default provider** ([OpenAI API Key](https://platform.openai.com/api-keys)). [Gemini](https://aistudio.google.com/apikey) and Anthropic Claude are also supported and provider-selectable.

### 1. Clone & Setup

```bash
git clone https://github.com/Yeshprabhu03/HireScope.git
cd HireScope
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# OpenAI is the default provider — set this key.
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o            # optional; override to use a newer model

# Other providers are optional (provider is selectable per request).
GEMINI_API_KEY=placeholder
GEMINI_MODEL=gemini-3.6-flash  # optional; override when Google retires a model
ANTHROPIC_API_KEY=placeholder
DATABASE_URL=postgresql://user:pass@localhost:5432/hirescope
ENV=development
DEBUG=true
CHROMA_PERSIST_DIR=./chroma_db
DOL_H1B_DATA_PATH=../data/h1b_data.csv
GLASSDOOR_CACHE_DIR=../data/interview_corpus
ALLOWED_ORIGINS=http://localhost:5173
USE_MOCK_DATA=false

# Security
HIRESCOPE_API_KEY=hirescope_dev_secret
```

### 3. Backend Setup
> [!IMPORTANT]
> All API requests now require the `X-API-Key` header for security.

```bash
cd backend
pip install -r requirements.txt
# Install pre-commit hooks for secret detection
pre-commit install
uvicorn main:app --reload --port 8000
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 5. Open the App

Navigate to **http://localhost:5173** and paste a job URL to analyze!

### 6. Remote Access (Optional)

To access the UI from a mobile device or external network, you can use [Pinggy](https://pinggy.io) to tunnel the local frontend instantly:

```bash
ssh -p 443 -o StrictHostKeyChecking=no -R0:localhost:5173 a.pinggy.io
```

## 🔧 Supported Job Boards

| Board | Method | Status |
|-------|--------|--------|
| Greenhouse | HTTP | ✅ Full support |
| Lever | HTTP | ✅ Full support |
| Indeed | HTTP | ✅ Full support |
| Eightfold | AI-Native JSON Extraction | ✅ Full support |
| Workday | AI-Native JSON Extraction | ✅ Full support |
| Next.js SPA | AI-Native JSON Extraction | ✅ Full support (e.g., Goldman Sachs) |
| Oracle Cloud | Playwright Rendering + Pruning | ✅ Full support |
| LinkedIn | Public Bypasses | ✅ Full support (Public Listings) |
| SmartRecruiters | Playwright | ✅ Full support |
| Generic URLs | HTTP + fallback | ✅ Best effort |

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Submit a job URL for analysis |
| `POST` | `/api/analyze/pdf` | Submit a PDF job description for analysis (multipart/form-data) |
| `GET` | `/api/jobs` | List all analyzed jobs |
| `GET` | `/api/jobs/{id}` | Get job status & progress |
| `GET` | `/api/jobs/{id}/report` | Get the HTML report |
| `POST` | `/api/jobs/{id}/feedback`| Submit thumbs up/down feedback for AI components |
| `POST` | `/api/rag/query` | Direct query endpoint for testing the local ChromaDB RAG |
| `GET` | `/health` | Health check |

## 🧪 Analysis Pipeline

The orchestrator runs a LangGraph pipeline with real-time progress tracking:

1. **🌐 Fetch Page** — Scrape HTML from the job URL (with a Chromium/Playwright auto-retry for JS-rendered SPAs)
2. **📋 Parse JD** — Extract structured data with the selected LLM
3. **🏢 Company Intel + 💰 Salary Data** — Run in parallel: company research and triangulated salary estimates
4. **🎯 Interview Prep** — Generate interview intelligence (RAG-backed)
5. **⚖️ Compatibility & Skill Gaps** — Score role fit and identify gaps
6. **📊 Generate Report** — Build the final HTML report

## 🛠️ Tech Stack

**Backend:** Python, FastAPI, LangGraph, ChromaDB, Pydantic, `yfinance`
**Frontend:** React, TypeScript, Vite, Tiptap, Recharts
**AI:** OpenAI GPT-4o (default), Google Gemini, Anthropic Claude — provider-selectable
**Data:** DOL H1B disclosures, Wikipedia API, RAG, Web Scrape

## 📝 License

**Proprietary and Confidential.**
All rights reserved. Unauthorized copying, modification, distribution, or use of this repository, via any medium, is strictly prohibited without explicit written permission.

---

Built with ❤️ by [@Yeshprabhu03](https://github.com/Yeshprabhu03)
