# HireScope — AI-Powered Job Intelligence Platform

Paste any job URL → get salary data, company insights, and interview prep in a beautiful HTML report.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                        │
│   JobInput → Dashboard → ReportViewer (TipTap editor)   │
└──────────────────┬──────────────────────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────────────────────┐
│              FastAPI Backend                            │
│  POST /api/analyze  →  BackgroundTasks                  │
│                              │                          │
│         ┌────────────────────▼─────────────────────┐   │
│         │        LangGraph Orchestrator             │   │
│         │                                           │   │
│         │  fetch_html → parse_jd → ┌─ fetch_company│   │
│         │                          ├─ fetch_salary  │   │
│         │                          └─ fetch_interviews│  │
│         │                                    ↓      │   │
│         │                           generate_report │   │
│         └───────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Claude API  │  │ DOL H1B CSV  │  │  ChromaDB RAG │  │
│  │ (JD parse,  │  │ (salary data)│  │ (interview Q) │  │
│  │  company AI)│  └──────────────┘  └───────────────┘  │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, LangGraph |
| AI | Anthropic Claude (sonnet-4), OpenAI embeddings |
| Vector DB | ChromaDB (interview RAG) |
| Data | DOL H1B CSV, Wikipedia API |
| Frontend | React 18, TypeScript, Vite, TipTap, Recharts |

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env — add ANTHROPIC_API_KEY and OPENAI_API_KEY

uvicorn main:app --reload
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs
```

**Mock mode** (no API keys needed):
```bash
# In .env:
USE_MOCK_DATA=true
```

### Index Interview Corpus

```bash
cd backend
python rag/vector_store.py --index
# Use --mock-embeddings if no OpenAI key
python rag/vector_store.py --index --mock-embeddings
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:5173
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Submit job URL, returns `job_id` |
| GET | `/api/jobs/{id}` | Poll job status |
| GET | `/api/jobs/{id}/report` | Get full HTML report |
| GET | `/api/jobs` | List all jobs |
| POST | `/api/rag/query` | Test RAG retrieval |
| GET | `/health` | Service health check |

### Example

```bash
# Submit a job
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"job_url": "https://www.linkedin.com/jobs/view/3874561234"}'
# → {"job_id": "uuid-here", "status": "created"}

# Poll status
curl http://localhost:8000/api/jobs/{job_id}
# → {"status": "completed", ...}

# Get report
curl http://localhost:8000/api/jobs/{job_id}/report
```

## Project Structure

```
hirescope/
├── backend/
│   ├── main.py              # FastAPI app, endpoints
│   ├── config.py            # Pydantic settings
│   ├── requirements.txt
│   ├── agents/
│   │   ├── orchestrator.py  # LangGraph workflow
│   │   ├── jd_parser.py     # Claude JD extraction
│   │   ├── salary_agent.py  # Salary triangulation
│   │   └── interview_agent.py # RAG interview Q&A
│   ├── data_sources/
│   │   ├── dol_h1b.py       # H1B salary data
│   │   ├── company_intel.py # Wikipedia + Claude
│   │   └── glassdoor.py     # Interview corpus loader
│   ├── rag/
│   │   ├── vector_store.py  # ChromaDB indexing
│   │   ├── embeddings.py    # OpenAI embeddings
│   │   └── retriever.py     # Semantic search
│   ├── output/
│   │   └── report_gen.py    # HTML report generation
│   └── utils/
│       └── job_fetcher.py   # URL → HTML scraper
├── frontend/
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── JobInput.tsx      # URL input form
│           ├── Dashboard.tsx     # Job list + status
│           └── ReportViewer.tsx  # Report + TipTap editor
└── data/
    ├── h1b_data.csv             # Sample H1B salary data
    └── interview_corpus/        # Interview JSON files
        ├── google_swe.json
        ├── amazon_sde.json
        └── meta_swe.json
```

## Key Design Decisions

### LangGraph Orchestration
The analysis pipeline uses LangGraph's state machine to run stages sequentially where dependent (fetch → parse) and in parallel where independent (company + salary + interviews all kick off after parsing).

### RAG for Interview Intelligence
Interview experiences from Glassdoor are chunked (500 chars), embedded with `text-embedding-3-small`, and stored in ChromaDB. At query time, 3 targeted queries retrieve relevant experiences which Claude synthesizes into structured insights.

### Salary Triangulation
Salary estimates combine 3 sources: (1) DOL H1B public disclosure data filtered by job title + company, (2) any salary mentioned in the JD, (3) Claude's market knowledge. A confidence score reflects how many sources contributed.

### Mock Mode
Set `USE_MOCK_DATA=true` for development without API keys. Every module has a mock fallback that returns realistic data.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | required |
| `OPENAI_API_KEY` | OpenAI embeddings key | required |
| `USE_MOCK_DATA` | Skip real API calls | `false` |
| `CHROMA_PERSIST_DIR` | ChromaDB storage path | `./chroma_db` |
| `DOL_H1B_DATA_PATH` | H1B CSV file path | `../data/h1b_data.csv` |
| `GLASSDOOR_CACHE_DIR` | Interview corpus dir | `../data/interview_corpus` |

## Testing Checklist

- [ ] Backend starts: `uvicorn main:app --reload`
- [ ] `/health` returns all services
- [ ] `POST /api/analyze` creates job with `status: created`
- [ ] Job progresses: `created → processing → completed`
- [ ] Parsed JD extracts job_title, company, skills
- [ ] Salary data returns estimated range
- [ ] Interview intel returns questions and tips
- [ ] HTML report renders all sections
- [ ] Frontend connects to API
- [ ] Dashboard polls job status
- [ ] Report viewer loads HTML in iframe
