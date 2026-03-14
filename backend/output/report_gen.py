import os
import jinja2
from datetime import datetime

logger = logging.getLogger(__name__)

# Setup Jinja2 Environment
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
template_loader = jinja2.FileSystemLoader(searchpath=TEMPLATE_DIR)
template_env = jinja2.Environment(
    loader=template_loader,
    autoescape=jinja2.select_autoescape(['html', 'xml']),
)

# Custom filter for JS-safe strings in buttons
def escape_js_filter(val):
    if not val:
        return ""
    return val.replace("'", "\\'").replace('"', '\\"')

template_env.filters['escape_js'] = escape_js_filter


def _fmt_currency(value) -> str:
    if value is None:
        return "N/A"
    try:
        return f"${int(value):,}"
    except Exception:
        return str(value)


def _salary_bar_svg(s_min: int, s_median: int, s_max: int) -> str:
    """Horizontal SVG bar chart for min / median / max salary."""
    if not s_max:
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
    model_name: str = "AI Assistant",
) -> str:
    """Generate a complete, styled HTML report using Jinja2 templates."""

    # Data preparation
    job_title = parsed_jd.get("job_title", "Unknown Position")
    company = parsed_jd.get("company", "Unknown Company")

    exp_min = parsed_jd.get("years_experience_min")
    exp_max = parsed_jd.get("years_experience_max")
    experience_str = (
        f"{exp_min}+" if exp_min and not exp_max
        else f"{exp_min}-{exp_max}" if exp_min and exp_max
        else "Not specified"
    )

    _s_min_raw = salary_intel.get("min", 0) or 0
    _s_max_raw = salary_intel.get("max", 0) or 0
    _s_med_raw = salary_intel.get("median", 0) or 0

    company_ticker = company_intel.get("ticker", "N/A")
    edgar_link = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={company_ticker}&type=10-K&action=getcompany" if company_ticker and company_ticker.upper() != "N/A" else None

    # Context for template
    context = {
        "job_id": job_id,
        "job_title": job_title,
        "company": company,
        "location": parsed_jd.get("location", "Unknown"),
        "seniority": parsed_jd.get("seniority_level", "mid").title(),
        "remote_policy": parsed_jd.get("remote_policy", "unknown").title(),
        "employment_type": parsed_jd.get("employment_type", "full-time").title(),
        "experience_str": experience_str,
        "model_name": model_name,

        "required_skills": parsed_jd.get("required_skills", []),
        "responsibilities": parsed_jd.get("key_responsibilities", []),

        "salary_min": _fmt_currency(_s_min_raw),
        "salary_median": _fmt_currency(_s_med_raw),
        "salary_max": _fmt_currency(_s_max_raw),
        "salary_range": salary_intel.get("estimated_range", "N/A"),
        "salary_confidence": int(float(salary_intel.get("confidence_score", 0)) * 100),
        "salary_data_label": salary_intel.get("data_label", ""),
        "salary_sources": salary_intel.get("sources_used", []),
        "salary_breakdown": salary_intel.get("breakdown", {}),
        "salary_chart_svg": _salary_bar_svg(_s_min_raw, _s_med_raw, _s_max_raw),

        "company_desc": company_intel.get("description", "No description available."),
        "company_ceo": company_intel.get("ceo", "N/A"),
        "company_industry": company_intel.get("industry", "Technology"),
        "company_hq": company_intel.get("headquarters", "N/A"),
        "company_employees": company_intel.get("employees", "N/A"),
        "company_source": company_intel.get("source", "Wikipedia API"),
        "company_market_cap": company_intel.get("market_cap", "N/A"),
        "company_business_unit": company_intel.get("business_unit_overview", "N/A"),
        "company_culture": company_intel.get("culture_highlights", []),
        "company_news": company_intel.get("recent_news", []),
        "company_networking": company_intel.get("linkedin_networking", "N/A"),
        "company_revenue_breakdown": company_intel.get("revenue_breakdown", []),
        "company_org_chart": company_intel.get("org_chart_mermaid", ""),
        "edgar_link": edgar_link,

        "interview_difficulty": interview_intel.get("difficulty", "unknown").title(),
        "interview_source_count": interview_intel.get("source_count", 0),
        "interview_data_warning": interview_intel.get("data_warning", False),
        "interview_confidence": int(float(interview_intel.get("confidence_score", 0.5)) * 100),
        "interview_source": interview_intel.get("source", ""),
        "interview_overview": interview_intel.get("process_overview", ""),
        "interview_rounds": interview_intel.get("rounds", []),
        "tech_questions": interview_intel.get("technical_questions", []),
        "behavioral_questions": interview_intel.get("behavioral_questions", []),
        "interview_tips": interview_intel.get("tips", []),
        "interview_platforms": interview_intel.get("identified_sources", []),
        "study_guide_sections": interview_intel.get("study_guide", []),

        "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
    }

    try:
        template = template_env.get_template("report.html")
        html = template.render(**context)
        logger.info(f"Generated HTML report for '{job_title}' at '{company}' using Jinja2 ({len(html)} chars)")
        return html
    except Exception as e:
        logger.error(f"Template rendering failed: {e}", exc_info=True)
        # Fallback to a simple error report if rendering fails
        return f"<h1>Error Generating Report</h1><p>{str(e)}</p>"

    logger.info(f"Generated HTML report for '{job_title}' at '{company}' ({len(html)} chars)")
    return html
