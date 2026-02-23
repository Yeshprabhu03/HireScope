# 🔍 HireScope — Job Intelligence in Seconds

HireScope is an AI-powered job analysis platform that transforms any job posting URL into a comprehensive intelligence report. Paste a link, get insights on salary, company culture, interview prep, and more.

![HireScope](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Gemini](https://img.shields.io/badge/AI-Gemini%202.0-4285F4)

## ✨ Features

- **🌐 Robust Job Page Scraping** — Fetches and parses job postings from any URL natively into structured JSON. Includes dynamic extraction strategies for Workday/Eightfold (`application/ld+json`) and Next.js SPAs like Goldman Sachs (`__NEXT_DATA__`) to bypass bot protection boundaries.
- **📋 JD Parsing** — AI-powered extraction of job title, company, skills, responsibilities, salary, and seniority.
- **🏢 Company Intelligence** — Real-time Market Cap integration via Yahoo Finance (`yfinance`) + Wikipedia data + AI-enriched insights (CEO, active Business Unit, Culture, and targeted LinkedIn Networking Strategies).
- **💰 Salary Intelligence** — Triangulated salary estimates from DOL H1B data, JD mentions, and AI market analysis.
- **🎯 High-Fidelity Mastery Roadmap** — Role-aware, dynamic RAG-powered interview intelligence featuring hierarchical technical/non-technical mastery categories, company-specific cultural values, and targeted gap analysis. Includes multi-platform data vetting (Reddit, WallStreetOasis, Exponent).
- **📊 Professional HTML Report** — Full-width, clean UI report with explicit source attribution and confidence indicators for generated intelligence.
- **⏱️ Real-Time Progress** — Live progress bar showing each analysis step as it completes

## 🧠 Continuous Learning Architecture (Updated Feb 22, 2026)

HireScope recently evolved from a stateless script into an intelligent, stateful system that learns and improves over time via a local SQLite database and dynamic ChromaDB (Vector Search) indexing.

- **Phase 1 (Data Caching)** — Eliminates redundant external API calls by caching parsed job descriptions and Wikipedia snapshots.
- **Phase 2 (Salary Intelligence)** — Automatically extracts explicit JD salary strings to build a proprietary baseline database, prioritizing "Learned Data" over DOL H1B data when 5+ observations are gathered for a role.
- **Phase 3 (Dynamic RAG Indexing)** — Intercepts sparse RAG searches. If there are `< 3` interview experiences for a company, the system live-scrapes the web, caches the data in SQLite, and injects the new vectors directly into the ChromaDB memory mid-flight. *Includes a strict real-time Vector Metadata Validation Algorithm that enforces deep word-overlap checks to guarantee role isolation and totally eliminate RAG cross-contamination.*
- **Phase 4 (User Feedback Loop)** — Provides explicit Thumbs-Up / Thumbs-Down buttons on generated Study Guides, logging user feedback ratings directly into SQLite for future fine-tuning to prune hallucinated vectors.

## 🏗️ Architecture

```
HireScope/
├── backend/                  # FastAPI + Python
│   ├── main.py               # API server & job orchestration
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
│   │   ├── llm.py            # Centralized Gemini API helper
│   │   └── job_fetcher.py    # URL scraping (requests + Playwright)
│   ├── rag/                  # RAG for interview experiences
│   └── output/
│       └── report_gen.py     # HTML report generator
├── frontend/                 # React + TypeScript + Vite
│   └── src/
│       └── components/
│           ├── Dashboard.tsx  # Job list with progress tracking
│           └── ReportViewer.tsx # Report display & editing
└── .env                      # API keys (not committed)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- [Gemini API Key](https://aistudio.google.com/apikey) (free)

### 1. Clone & Setup

```bash
git clone https://github.com/Yeshprabhu03/HireScope.git
cd HireScope
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=placeholder
OPENAI_API_KEY=placeholder
DATABASE_URL=postgresql://user:pass@localhost:5432/hirescope
ENV=development
DEBUG=true
CHROMA_PERSIST_DIR=./chroma_db
DOL_H1B_DATA_PATH=../data/h1b_data.csv
GLASSDOOR_CACHE_DIR=../data/interview_corpus
ALLOWED_ORIGINS=http://localhost:5173
USE_MOCK_DATA=false
```

### 3. Backend Setup

```bash
cd backend
pip install -r requirements.txt
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

## 🔧 Supported Job Boards

| Board | Method | Status |
|-------|--------|--------|
| Greenhouse | HTTP | ✅ Full support |
| Lever | HTTP | ✅ Full support |
| Indeed | HTTP | ✅ Full support |
| Eightfold | AI-Native JSON Extraction | ✅ Full support |
| Workday | AI-Native JSON Extraction | ✅ Full support |
| Next.js SPA | AI-Native JSON Extraction | ✅ Full support (e.g., Goldman Sachs) |
| LinkedIn | Public Bypasses | ✅ Full support (Public Listings) |
| SmartRecruiters | Playwright | ✅ Full support |
| Generic URLs | HTTP + fallback | ✅ Best effort |

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyze` | Submit a job URL for analysis |
| `GET` | `/api/jobs` | List all analyzed jobs |
| `GET` | `/api/jobs/{id}` | Get job status & progress |
| `GET` | `/api/jobs/{id}/report` | Get the HTML report |
| `GET` | `/health` | Health check |

## 🧪 Analysis Pipeline

The orchestrator runs 6 sequential steps with real-time progress tracking:

1. **🌐 Fetch Page** — Scrape HTML from the job URL
2. **📋 Parse JD** — Extract structured data with Gemini
3. **🏢 Company Intel** — Gather company information
4. **💰 Salary Data** — Triangulate salary estimates
5. **🎯 Interview Prep** — Generate interview intelligence
6. **📊 Generate Report** — Build the final HTML report

## 🛠️ Tech Stack

**Backend:** Python, FastAPI, LangGraph, ChromaDB, Pydantic, `yfinance`  
**Frontend:** React, TypeScript, Vite, Tiptap, Recharts  
**AI:** Google Gemini 2.0 Flash  
**Data:** DOL H1B disclosures, Wikipedia API, RAG, Web Scrape

## 📝 License

**Proprietary and Confidential.**  
All rights reserved. Unauthorized copying, modification, distribution, or use of this repository, via any medium, is strictly prohibited without explicit written permission.

---

Built with ❤️ by [@Yeshprabhu03](https://github.com/Yeshprabhu03)
