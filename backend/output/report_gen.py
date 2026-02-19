"""
Report Generator: produces a styled HTML report from all analysis modules.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _fmt_list(items: list, empty_msg: str = "Not available") -> str:
    if not items:
        return f"<li>{empty_msg}</li>"
    return "".join(f"<li>{item}</li>" for item in items)


def _fmt_currency(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${int(value):,}"
    except Exception:
        return str(value)


def _salary_bar_svg(s_min: int, s_median: int, s_max: int) -> str:
    """Horizontal SVG bar chart for min / median / max salary."""
    if s_max == 0:
        return ""
    chart_w, bar_h, gap, label_w = 420, 28, 10, 80

    def bar(value, color, label, y):
        pct = min(value / s_max, 1.0)
        bw = max(4, int(pct * chart_w))
        return (
            f'<text x="0" y="{y + bar_h // 2 + 5}" font-size="12" fill="#6b7280" '
            f'font-family="sans-serif">{label}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" fill="{color}" rx="4"/>'
            f'<text x="{label_w + bw + 6}" y="{y + bar_h // 2 + 5}" font-size="12" fill="#111827" '
            f'font-weight="600" font-family="sans-serif">${value:,}</text>'
        )

    svg_h = (bar_h + gap) * 3
    rows = (
        bar(s_min, "#93c5fd", "Min", 0)
        + bar(s_median, "#3b82f6", "Median", bar_h + gap)
        + bar(s_max, "#1d4ed8", "Max", 2 * (bar_h + gap))
    )
    return (
        f'<div style="margin: 16px 0;">'
        f'<svg width="{label_w + chart_w + 100}" height="{svg_h}" '
        f'xmlns="http://www.w3.org/2000/svg">{rows}</svg></div>'
    )


def generate_html_report(
    parsed_jd: dict,
    company_intel: dict,
    salary_intel: dict,
    interview_intel: dict,
    job_id: str = "",
    analysis_start: float = 0.0,
) -> str:
    """Generate a complete, styled HTML report from all analysis data."""

    job_title = parsed_jd.get("job_title", "Unknown Position")
    company = parsed_jd.get("company", "Unknown Company")
    location = parsed_jd.get("location", "Unknown")
    seniority = parsed_jd.get("seniority_level", "mid").title()
    remote_policy = parsed_jd.get("remote_policy", "unknown").title()
    employment_type = parsed_jd.get("employment_type", "full-time").title()
    required_skills = parsed_jd.get("required_skills", [])
    responsibilities = parsed_jd.get("key_responsibilities", [])
    exp_min = parsed_jd.get("years_experience_min")
    exp_max = parsed_jd.get("years_experience_max")
    experience_str = (
        f"{exp_min}+" if exp_min and not exp_max
        else f"{exp_min}-{exp_max}" if exp_min and exp_max
        else "Not specified"
    )

    salary_range = salary_intel.get("estimated_range", "N/A")
    _s_min_raw = salary_intel.get("min", 0) or 0
    _s_max_raw = salary_intel.get("max", 0) or 0
    _s_med_raw = salary_intel.get("median", 0) or 0
    salary_median = _fmt_currency(_s_med_raw)
    salary_min = _fmt_currency(_s_min_raw)
    salary_max = _fmt_currency(_s_max_raw)
    salary_confidence = int(float(salary_intel.get("confidence_score", 0)) * 100)
    salary_sources = salary_intel.get("sources_used", [])
    salary_breakdown = salary_intel.get("breakdown", {})
    salary_data_label = salary_intel.get("data_label", "")
    salary_chart_svg = _salary_bar_svg(_s_min_raw, _s_med_raw, _s_max_raw)

    company_desc = company_intel.get("description", "No description available.")
    company_ceo = company_intel.get("ceo", "N/A")
    company_hq = company_intel.get("headquarters", "N/A")
    company_employees = company_intel.get("employees", "N/A")
    company_revenue = company_intel.get("revenue", "N/A")
    company_industry = company_intel.get("industry", "Technology")
    company_culture = company_intel.get("culture_highlights", [])
    company_news = company_intel.get("recent_news", [])

    interview_rounds = interview_intel.get("rounds", [])
    tech_questions = interview_intel.get("technical_questions", [])
    behavioral_questions = interview_intel.get("behavioral_questions", [])
    interview_difficulty = interview_intel.get("difficulty", "unknown").title()
    interview_tips = interview_intel.get("tips", [])
    interview_overview = interview_intel.get("process_overview", "")
    interview_source = interview_intel.get("source", "")
    interview_data_warning = interview_intel.get("data_warning", False)

    generated_at = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    skill_badges = "".join(
        f'<span class="badge">{skill}</span>' for skill in required_skills
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{job_title} at {company} — HireScope Report</title>
  <style>
    :root {{
      --primary: #2563eb;
      --primary-light: #eff6ff;
      --secondary: #7c3aed;
      --success: #16a34a;
      --warning: #d97706;
      --danger: #dc2626;
      --gray-50: #f9fafb;
      --gray-100: #f3f4f6;
      --gray-200: #e5e7eb;
      --gray-600: #4b5563;
      --gray-700: #374151;
      --gray-900: #111827;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--gray-900);
      background: var(--gray-50);
      line-height: 1.6;
    }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}

    /* Header */
    .report-header {{
      background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
      color: white;
      padding: 32px;
      border-radius: 12px;
      margin-bottom: 24px;
    }}
    .report-header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
    .report-header h2 {{ font-size: 20px; font-weight: 400; opacity: 0.9; margin-bottom: 16px; }}
    .meta-tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .meta-tag {{
      background: rgba(255,255,255,0.2);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 13px;
    }}

    /* Cards */
    .card {{
      background: white;
      border-radius: 10px;
      border: 1px solid var(--gray-200);
      padding: 24px;
      margin-bottom: 20px;
    }}
    .card-title {{
      font-size: 18px;
      font-weight: 600;
      color: var(--primary);
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--primary-light);
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    /* Salary section */
    .salary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }}
    .salary-stat {{
      background: var(--gray-50);
      border: 1px solid var(--gray-200);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }}
    .salary-stat .value {{ font-size: 22px; font-weight: 700; color: var(--success); }}
    .salary-stat .label {{ font-size: 12px; color: var(--gray-600); margin-top: 4px; }}
    .confidence-bar {{
      background: var(--gray-200);
      border-radius: 4px;
      height: 8px;
      margin-top: 8px;
      overflow: hidden;
    }}
    .confidence-fill {{
      background: var(--success);
      height: 100%;
      border-radius: 4px;
    }}

    /* Badges */
    .badge {{
      display: inline-block;
      background: var(--primary-light);
      color: var(--primary);
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      margin: 3px;
    }}
    .badge-warning {{
      background: #fffbeb;
      color: var(--warning);
    }}

    /* Lists */
    .styled-list {{ list-style: none; padding: 0; }}
    .styled-list li {{
      padding: 8px 0;
      border-bottom: 1px solid var(--gray-100);
      padding-left: 20px;
      position: relative;
    }}
    .styled-list li::before {{
      content: "▸";
      color: var(--primary);
      position: absolute;
      left: 0;
    }}
    .styled-list li:last-child {{ border-bottom: none; }}

    /* Grid layouts */
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    .company-info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .info-row {{ display: flex; flex-direction: column; padding: 8px; background: var(--gray-50); border-radius: 6px; }}
    .info-label {{ font-size: 11px; color: var(--gray-600); text-transform: uppercase; font-weight: 600; }}
    .info-value {{ font-size: 14px; color: var(--gray-900); margin-top: 2px; }}

    /* Difficulty badge */
    .difficulty-hard {{ background: #fef2f2; color: var(--danger); }}
    .difficulty-medium {{ background: #fffbeb; color: var(--warning); }}
    .difficulty-easy {{ background: #f0fdf4; color: var(--success); }}

    /* Interview rounds */
    .rounds-list {{ display: flex; flex-direction: column; gap: 8px; }}
    .round-item {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      background: var(--gray-50);
      border-radius: 8px;
      border-left: 4px solid var(--primary);
    }}
    .round-num {{
      background: var(--primary);
      color: white;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 700;
      flex-shrink: 0;
    }}

    /* Footer */
    .report-footer {{
      text-align: center;
      padding: 24px;
      color: var(--gray-600);
      font-size: 13px;
    }}

    @media (max-width: 640px) {{
      .salary-grid {{ grid-template-columns: 1fr; }}
      .two-col {{ grid-template-columns: 1fr; }}
      .company-info-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="report-header">
    <h1>{job_title}</h1>
    <h2>{company}</h2>
    <div class="meta-tags">
      <span class="meta-tag">📍 {location}</span>
      <span class="meta-tag">⭐ {seniority}</span>
      <span class="meta-tag">🏠 {remote_policy}</span>
      <span class="meta-tag">💼 {employment_type}</span>
      <span class="meta-tag">⏱ {experience_str} years exp</span>
    </div>
  </div>

  <!-- Skills -->
  <div class="card">
    <div class="card-title">🛠 Required Skills</div>
    <div>{skill_badges if skill_badges else '<span class="badge badge-warning">Not specified</span>'}</div>
  </div>

  <!-- Responsibilities -->
  <div class="card">
    <div class="card-title">📋 Key Responsibilities</div>
    <ul class="styled-list">
      {_fmt_list(responsibilities)}
    </ul>
  </div>

  <!-- Salary Intelligence -->
  <div class="card">
    <div class="card-title">💰 Salary Intelligence</div>
    <div class="salary-grid">
      <div class="salary-stat">
        <div class="value">{salary_min}</div>
        <div class="label">Minimum</div>
      </div>
      <div class="salary-stat">
        <div class="value">{salary_median}</div>
        <div class="label">Median</div>
      </div>
      <div class="salary-stat">
        <div class="value">{salary_max}</div>
        <div class="label">Maximum</div>
      </div>
    </div>
    {salary_chart_svg}
    <p style="color: var(--gray-600); font-size: 14px; margin-bottom: 4px;">
      <strong>Estimated Range:</strong> {salary_range}
    </p>
    {f'<p style="color: #d97706; font-size: 13px; margin-bottom: 4px;">⚠ {salary_data_label}</p>' if salary_data_label else ''}
    <p style="color: var(--gray-600); font-size: 13px; margin-bottom: 4px;">
      Data confidence: {salary_confidence}%
    </p>
    <div class="confidence-bar">
      <div class="confidence-fill" style="width: {salary_confidence}%"></div>
    </div>
    <p style="color: var(--gray-600); font-size: 13px; margin-top: 8px;">
      Sources: {", ".join(salary_sources) if salary_sources else "Market estimate only"}
    </p>
    {f'''
    <div style="margin-top: 16px;">
      <strong style="font-size: 14px;">Compensation Breakdown</strong>
      <table style="width: 100%; margin-top: 8px; border-collapse: collapse; font-size: 13px;">
        {"".join(f'<tr><td style="padding: 6px 0; color: var(--gray-600); border-bottom: 1px solid var(--gray-100);">{k.replace("_", " ").title()}</td><td style="padding: 6px 0; font-weight: 500; border-bottom: 1px solid var(--gray-100);">{v}</td></tr>' for k, v in salary_breakdown.items())}
      </table>
    </div>
    ''' if salary_breakdown else ''}
  </div>

  <!-- Company Intelligence -->
  <div class="card">
    <div class="card-title">🏢 Company Intelligence</div>
    <p style="color: var(--gray-700); margin-bottom: 16px; font-size: 14px;">{company_desc}</p>
    <div class="company-info-grid" style="margin-bottom: 16px;">
      <div class="info-row">
        <span class="info-label">CEO</span>
        <span class="info-value">{company_ceo}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Industry</span>
        <span class="info-value">{company_industry}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Headquarters</span>
        <span class="info-value">{company_hq}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Employees</span>
        <span class="info-value">{company_employees}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Revenue</span>
        <span class="info-value">{company_revenue}</span>
      </div>
    </div>
    <div class="two-col">
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">🌱 Culture</strong>
        <ul class="styled-list">
          {_fmt_list(company_culture, "No culture data available")}
        </ul>
      </div>
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">📰 Recent News</strong>
        <ul class="styled-list">
          {_fmt_list(company_news, "No recent news available")}
        </ul>
      </div>
    </div>
  </div>

  <!-- Interview Intelligence -->
  <div class="card">
    <div class="card-title">🎯 Interview Intelligence</div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <span class="badge difficulty-{interview_difficulty.lower()}" style="font-size: 13px; padding: 4px 14px;">
        Difficulty: {interview_difficulty}
      </span>
    </div>
    {f'<div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;padding:10px 14px;margin-bottom:12px;font-size:13px;color:#92400e;">⚠ {interview_source}</div>' if interview_data_warning else f'<p style="font-size:13px;color:var(--gray-600);margin-bottom:12px;">Source: {interview_source}</p>'}

    {f'<p style="color: var(--gray-700); font-size: 14px; margin-bottom: 16px;">{interview_overview}</p>' if interview_overview else ''}

    <div style="margin-bottom: 20px;">
      <strong style="font-size: 14px; display: block; margin-bottom: 10px;">📅 Interview Process</strong>
      <div class="rounds-list">
        {"".join(f'<div class="round-item"><div class="round-num">{i+1}</div><span style="font-size: 14px;">{r}</span></div>' for i, r in enumerate(interview_rounds))}
      </div>
    </div>

    <div class="two-col">
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">💻 Technical Questions</strong>
        <ul class="styled-list">
          {_fmt_list(tech_questions)}
        </ul>
      </div>
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">🤝 Behavioral Questions</strong>
        <ul class="styled-list">
          {_fmt_list(behavioral_questions)}
        </ul>
      </div>
    </div>

    <div style="margin-top: 20px;">
      <strong style="font-size: 14px; display: block; margin-bottom: 8px;">💡 Preparation Tips</strong>
      <ul class="styled-list">
        {_fmt_list(interview_tips)}
      </ul>
    </div>
  </div>

  <!-- Metadata -->
  <div class="card" style="background: var(--gray-50); border-style: dashed;">
    <div class="card-title" style="font-size: 14px; color: var(--gray-600);">📋 Analysis Metadata</div>
    <div class="company-info-grid">
      <div class="info-row">
        <span class="info-label">Job ID</span>
        <span class="info-value" style="font-family: monospace; font-size: 12px;">{job_id or "N/A"}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Generated</span>
        <span class="info-value">{generated_at}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Salary Confidence</span>
        <span class="info-value">{salary_confidence}% — {salary_data_label or "Market estimate"}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Data Sources</span>
        <span class="info-value">{", ".join(salary_sources) if salary_sources else "Market estimate"}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Interview Data</span>
        <span class="info-value">{"AI-generated guide" if interview_data_warning else "RAG corpus"}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Company Source</span>
        <span class="info-value">{company_intel.get("source", "N/A")}</span>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="report-footer">
    <p>Generated by <strong>HireScope</strong> on {generated_at}</p>
    <p style="margin-top: 4px; font-size: 12px;">
      AI-powered job intelligence. Salary from DOL H1B disclosures + Gemini. Company from Wikipedia + Gemini. Interviews from corpus + Gemini.
    </p>
  </div>

</div>
</body>
</html>"""

    logger.info(f"Generated HTML report for '{job_title}' at '{company}' ({len(html)} chars)")
    return html
