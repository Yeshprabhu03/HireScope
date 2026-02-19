# 🔍 HireScope — Job Intelligence in Seconds

HireScope is an AI-powered job analysis platform that transforms any job posting URL into a comprehensive intelligence report. Paste a link, get insights on salary, company culture, interview prep, and more.

![HireScope](https://img.shields.io/badge/Status-Active%20Development-brightgreen)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Gemini](https://img.shields.io/badge/AI-Gemini%202.0-4285F4)

## ✨ Features

- **🌐 Job Page Scraping** — Fetches and parses job postings from any URL (Greenhouse, Lever, Indeed, Eightfold, LinkedIn, and more)
- **📋 JD Parsing** — AI-powered extraction of job title, company, skills, responsibilities, salary, and seniority
- **🏢 Company Intelligence** — Wikipedia data + AI-enriched insights (CEO, culture, business model, recent news)
- **💰 Salary Intelligence** — Triangulated salary estimates from DOL H1B data, JD mentions, and AI market analysis
- **🎯 Interview Prep** — RAG-powered interview intelligence with technical/behavioral questions and prep tips
- **📊 HTML Report** — Beautiful, printable/PDF-ready report with all findings
- **⏱️ Real-Time Progress** — Live progress bar showing each analysis step as it completes

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
playwright install chromium
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
| Eightfold | Playwright | ✅ Full support |
| Workday | Playwright | ✅ Full support |
| LinkedIn | Playwright | ⚠️ May require login |
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

**Backend:** Python, FastAPI, LangGraph, Playwright, ChromaDB, Pydantic  
**Frontend:** React, TypeScript, Vite, Tiptap, Recharts  
**AI:** Google Gemini 2.0 Flash  
**Data:** DOL H1B disclosures, Wikipedia API, ChromaDB RAG

## 📝 License

MIT

---

Built with ❤️ by [@Yeshprabhu03](https://github.com/Yeshprabhu03)
