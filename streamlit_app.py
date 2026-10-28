"""
HireScope — Streamlit UI.

A standalone front-end that drives the full analysis pipeline IN-PROCESS (no
FastAPI server needed): it imports the LangGraph orchestrator directly, runs it
in a background thread, streams live progress, and renders the generated HTML
report.

Run:
    pip install streamlit        # one-time
    # ensure .env has OPENAI_API_KEY (default provider)
    streamlit run streamlit_app.py
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

st.markdown(
    """
    <style>
      .hs-title { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0; }
      .hs-sub { color: #6b6f80; margin-top: 0.1rem; }
      .stProgress > div > div > div { background-image: linear-gradient(90deg,#4338ca,#8b74ff); }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="hs-title">🔍 HireScope</div>', unsafe_allow_html=True)
st.markdown('<div class="hs-sub">Paste a job link (or upload the JD as a PDF) → a full intelligence report.</div>', unsafe_allow_html=True)
st.write("")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Settings")
    provider_label = st.selectbox("LLM provider", list(PROVIDERS.keys()), index=0)
    provider = PROVIDERS[provider_label]

    st.caption("Optional — paste your resume / skills for a personalized fit & gap analysis.")
    user_context = st.text_area("Your background", height=140, placeholder="e.g. 6 yrs backend (Python, Kafka, AWS)...")

    st.divider()
    st.caption("Keys are read from `.env`. OpenAI is the default provider; "
               "market cap uses Finnhub when `FINNHUB_API_KEY` is set (else Yahoo).")


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
mode = st.radio("Source", ["Job URL", "PDF upload"], horizontal=True, label_visibility="collapsed")

job_url = ""
pdf_file = None
if mode == "Job URL":
    job_url = st.text_input("Job posting URL", placeholder="https://company.com/careers/job/12345")
else:
    pdf_file = st.file_uploader("Upload a job-description PDF", type=["pdf"])

analyze = st.button("Analyze", type="primary", use_container_width=True)

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
