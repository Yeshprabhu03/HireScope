"""
HireScope — Streamlit UI.

A standalone front-end that drives the full analysis pipeline IN-PROCESS (no
FastAPI server needed): it imports the LangGraph orchestrator directly, runs it
in a background thread, streams live progress, and renders the generated HTML
report. Styled to match the React app (gradient header, Outfit/Inter, indigo
accent).

Run locally:
    pip install -r requirements.txt   # one-time (pulls backend stack + streamlit)
    # ensure .env has OPENAI_API_KEY (default provider)
    streamlit run streamlit_app.py

Deploy (Streamlit Community Cloud): point it at streamlit_app.py and set
OPENAI_API_KEY in the app's Secrets. See the README "Deploy the Streamlit app".
"""
import asyncio
import io
import os
import sys
import threading
import time
import uuid

import streamlit as st
import streamlit.components.v1 as components

# On Streamlit Community Cloud there is no .env file — secrets live in the app's
# Secrets manager. Bridge them into the environment so the backend's pydantic
# config (which reads os.environ) picks them up. No-op locally where .env is used.
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

# Make the backend package importable (agents/, data_sources/, utils/, ...).
_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from agents.orchestrator import run_job_analysis  # noqa: E402

PROVIDERS = {
    "OpenAI · GPT-4o": "openai",
    "Google · Gemini": "gemini",
    "Anthropic · Claude": "anthropic",
}

st.set_page_config(page_title="HireScope", page_icon="🔍", layout="wide")

# ── Theme — mirror the React app's design tokens ──────────────────────────────
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700;800&display=swap');
      :root {
        --bg-main:#f1f5f9; --bg-card:#ffffff; --accent:#4f46e5; --accent-dark:#4338ca;
        --text-main:#1e293b; --text-muted:#64748b; --border:#e2e8f0;
        --grad:linear-gradient(135deg,#6366f1 0%,#a855f7 100%);
      }
      .stApp { background: var(--bg-main); }
      #MainMenu, footer { visibility: hidden; }
      [data-testid="stHeader"] { background: transparent; height: 0; }
      html, body, .stApp, [data-testid="stMarkdownContainer"] p, label, input, textarea, .stRadio {
        font-family: 'Inter', system-ui, sans-serif; color: var(--text-main);
      }
      h1, h2, h3, h4 { font-family: 'Outfit', sans-serif !important; color: var(--text-main); }
      .block-container { padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1080px; }

      /* Gradient header banner (matches the React top bar) */
      .hs-header {
        background: var(--grad); border-radius: 16px; padding: 22px 28px; margin-bottom: 24px;
        box-shadow: 0 12px 34px rgba(124,74,247,.28); display: flex; align-items: center; justify-content: space-between;
      }
      .hs-header .brand { font-family:'Outfit',sans-serif; font-weight:800; font-size:1.65rem; color:#fff; letter-spacing:-.02em; }
      .hs-header .tag { color: rgba(255,255,255,.88); font-size:.95rem; margin-top:3px; font-weight:500; }
      .hs-header .pill { color:#fff; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.28);
        padding:7px 16px; border-radius:999px; font-weight:600; font-size:.85rem; }

      /* Section heading ("My Jobs Vault" style) */
      .hs-h { font-family:'Outfit',sans-serif; font-weight:800; font-size:1.7rem; margin:.1rem 0 .1rem; }
      .hs-sub { color: var(--text-muted); margin:0 0 1.1rem; }

      /* Buttons */
      .stButton > button {
        background: var(--accent); color:#fff; border:none; border-radius:10px; font-weight:600;
        font-family:'Outfit',sans-serif; padding:.6rem 1.3rem; transition: all .15s;
      }
      .stButton > button:hover { background: var(--accent-dark); color:#fff; transform: translateY(-1px); }
      .stButton > button[kind="primary"] { background-image: var(--grad); box-shadow:0 6px 18px rgba(124,74,247,.3); }

      /* Inputs */
      [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
        background: var(--bg-card) !important; border:1px solid var(--border) !important; border-radius:10px !important;
      }
      [data-baseweb="select"] > div { background: var(--bg-card) !important; border:1px solid var(--border) !important; border-radius:10px !important; }
      [data-testid="stFileUploaderDropzone"] { background: var(--bg-card); border:1px dashed #c7cedb; border-radius:12px; }

      /* Metric cards */
      [data-testid="stMetric"] {
        background: var(--bg-card); border:1px solid var(--border); border-radius:14px;
        padding:14px 16px; box-shadow:0 1px 2px rgba(15,23,42,.05);
      }
      [data-testid="stMetricLabel"] p { color: var(--text-muted); font-weight:600; }
      [data-testid="stMetricValue"] { font-family:'Outfit',sans-serif; font-size:1.25rem; }

      /* Progress bar → brand gradient */
      .stProgress > div > div > div { background-image: var(--grad); }

      /* Sidebar as a card rail */
      [data-testid="stSidebar"] { background: var(--bg-card); border-right:1px solid var(--border); }
      [data-testid="stSidebar"] h3 { font-family:'Outfit',sans-serif; }

      /* Report iframe gets a card frame */
      iframe { border:1px solid var(--border); border-radius:14px; background:#fff; box-shadow:0 1px 2px rgba(15,23,42,.05); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hs-header">
      <div>
        <div class="brand">🔍 HireScope</div>
        <div class="tag">Job intelligence in seconds — paste a link, get the full report.</div>
      </div>
      <div class="pill">AI-Powered</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    provider_label = st.selectbox("LLM provider", list(PROVIDERS.keys()), index=0)
    provider = PROVIDERS[provider_label]

    st.caption("Optional — paste your resume / skills for a personalized fit & gap analysis.")
    user_context = st.text_area("Your background", height=140, placeholder="e.g. 6 yrs backend (Python, Kafka, AWS)...")

    st.divider()
    st.caption("Keys are read from `.env` locally, or the app's Secrets on "
               "Streamlit Cloud. OpenAI is the default provider.")


def _extract_pdf_text(file) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(file.read()))
    return "\n".join((p.extract_text() or "") for p in reader.pages).strip()


def _run_pipeline(job_id, job_url, provider, jobs, uploaded_text, user_context, holder):
    """Run the async orchestrator in its own event loop (background thread)."""
    try:
        holder["result"] = asyncio.run(
            run_job_analysis(
                job_id=job_id,
                job_url=job_url,
                provider=provider,
                jobs=jobs,
                uploaded_text=uploaded_text,
                user_context=user_context or None,
            )
        )
    except Exception as e:  # surface any hard failure to the UI thread
        holder["result"] = {"status": "failed", "error": str(e)}


# ── Input ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="hs-h">Analyze a Job</div>', unsafe_allow_html=True)
st.markdown('<div class="hs-sub">Turn any job posting into a comprehensive intelligence report.</div>', unsafe_allow_html=True)

mode = st.radio("Source", ["Job URL", "PDF upload"], horizontal=True, label_visibility="collapsed")

job_url = ""
pdf_file = None
if mode == "Job URL":
    job_url = st.text_input("Job posting URL", placeholder="https://company.com/careers/job/12345", label_visibility="collapsed")
else:
    pdf_file = st.file_uploader("Upload a job-description PDF", type=["pdf"])

analyze = st.button("🔍  Analyze", type="primary", use_container_width=True)

# ── Run ───────────────────────────────────────────────────────────────────────
if analyze:
    uploaded_text = None
    effective_url = job_url.strip()
    if mode == "PDF upload":
        if not pdf_file:
            st.warning("Please upload a PDF first.")
            st.stop()
        with st.spinner("Reading PDF…"):
            uploaded_text = _extract_pdf_text(pdf_file)
        effective_url = f"upload://{pdf_file.name}"
        if not uploaded_text:
            st.error("Couldn't extract any text from that PDF.")
            st.stop()
    elif not effective_url:
        st.warning("Please enter a job URL.")
        st.stop()

    job_id = str(uuid.uuid4())
    jobs = {job_id: {}}
    holder: dict = {}

    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, effective_url, provider, jobs, uploaded_text, user_context, holder),
        daemon=True,
    )
    t.start()

    progress_bar = st.progress(0)
    status = st.empty()
    while t.is_alive():
        prog = jobs.get(job_id, {}).get("progress", {}) or {}
        progress_bar.progress(min(int(prog.get("percent", 0)), 100))
        status.info(prog.get("current_step_label", "⏳ Starting analysis…"))
        time.sleep(0.4)
    t.join()

    result = holder.get("result") or {}
    progress_bar.progress(100)

    if result.get("status") == "failed":
        status.error(f"Analysis failed: {result.get('error', 'unknown error')}")
        st.stop()

    status.success("✅ Analysis complete")

    # Headline metrics
    jd = result.get("parsed_jd") or {}
    comp = result.get("company_intelligence") or {}
    sal = result.get("salary_intelligence") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Role", jd.get("job_title", "—"))
    c2.metric("Company", jd.get("company", "—"))
    c3.metric("Market cap", comp.get("market_cap", "—"))
    c4.metric("Salary range", sal.get("estimated_range", "—"))

    # Full HTML report
    html_report = result.get("html_report") or ""
    if html_report:
        components.html(html_report, height=1600, scrolling=True)
    else:
        st.info("No HTML report was generated.")
else:
    st.caption("Tip: Greenhouse, Lever and Workday links all work. SPA job boards "
               "use a headless browser — run `playwright install chromium` locally if a link won't render.")
