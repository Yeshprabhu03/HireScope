import os
import logging
import jinja2
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Template loading ──────────────────────────────────────────────────────────
# Try file-system first (local dev); fall back to the copy embedded below
# so the app works even when the templates/ directory is missing from the image.

def _load_template_source() -> str:
    """Return the Jinja2 template source, preferring the file on disk."""
    candidate = Path(__file__).resolve().parent.parent / "templates" / "report.html"
    if candidate.exists():
        logger.info(f"Loading report template from disk: {candidate}")
        return candidate.read_text(encoding="utf-8")
    logger.warning("report.html not found on disk — using embedded template")
    return _EMBEDDED_REPORT_TEMPLATE


# ── Jinja2 env (BaseLoader so we can render from a string) ───────────────────
template_env = jinja2.Environment(
    loader=jinja2.BaseLoader(),
    autoescape=jinja2.select_autoescape(['html', 'xml']),
)

# Custom filter for JS-safe strings in buttons
def escape_js_filter(val):
    if not val:
        return ""
    return val.replace("'", "\\'").replace('"', '\\"')

template_env.filters['escape_js'] = escape_js_filter

# ── Embedded template (verbatim copy of backend/templates/report.html) ───────
_EMBEDDED_REPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{ company }} - {{ job_title }}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({ startOnLoad: true, theme: 'neutral' });</script>
  <style>
    :root {
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
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--gray-900);
      background: var(--gray-50);
      line-height: 1.6;
    }
    .container { max-width: 100%; margin: 0 auto; padding: 24px 32px; }

    /* Header */
    .report-header {
      background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
      color: white;
      padding: 32px;
      border-radius: 12px;
      margin-bottom: 24px;
    }
    .report-header h1 { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
    .report-header h2 { font-size: 20px; font-weight: 400; opacity: 0.9; margin-bottom: 16px; }
    .meta-tags { display: flex; flex-wrap: wrap; gap: 8px; }
    .meta-tag {
      background: rgba(255,255,255,0.2);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 13px;
    }

    /* Cards */
    .card {
      background: white;
      border-radius: 10px;
      border: 1px solid var(--gray-200);
      padding: 24px;
      margin-bottom: 20px;
    }
    .card-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--primary);
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--primary-light);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Salary section */
    .salary-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
    .salary-stat {
      background: var(--gray-50);
      border: 1px solid var(--gray-200);
      border-radius: 8px;
      padding: 16px;
      text-align: center;
    }
    .salary-stat .value { font-size: 22px; font-weight: 700; color: var(--success); }
    .salary-stat .label { font-size: 12px; color: var(--gray-600); margin-top: 4px; }
    .confidence-bar {
      background: var(--gray-200);
      border-radius: 4px;
      height: 8px;
      margin-top: 8px;
      overflow: hidden;
    }
    .confidence-fill {
      background: var(--success);
      height: 100%;
      border-radius: 4px;
    }

    /* Badges */
    .badge {
      display: inline-block;
      background: var(--primary-light);
      color: var(--primary);
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      margin: 3px;
    }
    .badge-warning {
      background: #fffbeb;
      color: var(--warning);
    }

    /* Lists */
    .styled-list { list-style: none; padding: 0; }
    .styled-list li {
      padding: 8px 0;
      border-bottom: 1px solid var(--gray-100);
      padding-left: 20px;
      position: relative;
    }
    .styled-list li::before {
      content: "▸";
      color: var(--primary);
      position: absolute;
      left: 0;
    }
    .styled-list li:last-child { border-bottom: none; }

    /* Grid layouts */
    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .company-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .info-row { display: flex; flex-direction: column; padding: 8px; background: var(--gray-50); border-radius: 6px; }
    .info-label { font-size: 11px; color: var(--gray-600); text-transform: uppercase; font-weight: 600; }
    .info-value { font-size: 14px; color: var(--gray-900); margin-top: 2px; }

    /* Difficulty badge */
    .difficulty-hard { background: #fef2f2; color: var(--danger); }
    .difficulty-medium { background: #fffbeb; color: var(--warning); }
    .difficulty-easy { background: #f0fdf4; color: var(--success); }

    /* Interview rounds */
    .rounds-list { display: flex; flex-direction: column; gap: 8px; }
    .round-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 14px;
      background: var(--gray-50);
      border-radius: 8px;
      border-left: 4px solid var(--primary);
    }
    .round-num {
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
    }

    /* Footer */
    .report-footer {
      text-align: center;
      padding: 24px;
      color: var(--gray-600);
      font-size: 13px;
    }

    @media (max-width: 640px) {
      .salary-grid { grid-template-columns: 1fr; }
      .two-col { grid-template-columns: 1fr; }
      .company-info-grid { grid-template-columns: 1fr; }
    }
    .mermaid {
      text-align: center;
    }
    /* Compatibility & Grade */
    .grade-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      font-size: 24px;
      font-weight: 800;
      color: white;
      text-shadow: 0 1px 2px rgba(0,0,0,0.1);
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .grade-A { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
    .grade-B { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
    .grade-C { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
    .grade-D { background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }
    .grade-F { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }

    .dimension-bar-container { background: var(--gray-100); height: 6px; border-radius: 3px; margin-top: 4px; overflow: hidden; width: 100%; }
    .dimension-bar-fill { height: 100%; border-radius: 3px; background: var(--primary); }

    .gap-item { padding: 12px; border-radius: 8px; border: 1px solid var(--gray-200); background: white; margin-bottom: 8px; }
    .gap-priority-high { border-left: 4px solid var(--danger); }
    .gap-priority-medium { border-left: 4px solid var(--warning); }
    .gap-priority-low { border-left: 4px solid var(--success); }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({startOnLoad:true});</script>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="report-header">
    <h1>{{ job_title }}</h1>
    <h2>{{ company }}</h2>
    <div class="meta-tags">
      <span class="meta-tag">Location: {{ location }}</span>
      <span class="meta-tag">Level: {{ seniority }}</span>
      <span class="meta-tag">Remote: {{ remote_policy }}</span>
      <span class="meta-tag">Type: {{ employment_type }}</span>
      <span class="meta-tag">Exp: {{ experience_str }} years</span>
      <span class="meta-tag">Model: {{ model_name }}</span>
    </div>
  </div>

  <!-- Compatibility Intelligence -->
  {% if compatibility %}
  <div class="card" style="border: 2px solid var(--primary-light); background: linear-gradient(to bottom right, #fff, #f8fafc);">
    <div style="display: flex; align-items: flex-start; gap: 24px;">
      <div class="grade-badge grade-{{ compatibility.overall_grade[0] | upper }}">
        {{ compatibility.overall_grade }}
      </div>
      <div style="flex: 1;">
        <div class="card-title" style="border: none; margin-bottom: 4px; padding: 0;">Compatibility & Fit Score</div>
        <p style="font-size: 14px; color: var(--gray-700); margin-bottom: 16px;">{{ compatibility.overall_reasoning }}</p>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;">
          {% for dim in compatibility.dimensions %}
          <div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; color: var(--gray-600);">
              <span>{{ dim.name }}</span>
              <span>{{ dim.score }}%</span>
            </div>
            <div class="dimension-bar-container">
              <div class="dimension-bar-fill" style="width: {{ dim.score }}%; background: {% if dim.score > 80 %}#10b981{% elif dim.score > 60 %}#3b82f6{% elif dim.score > 40 %}#f59e0b{% else %}#ef4444{% endif %};"></div>
            </div>
            <p style="font-size: 11px; color: var(--gray-500); margin-top: 4px; font-style: italic;">{{ dim.reasoning }}</p>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>
  {% endif %}

  <!-- Company Intelligence -->
  <div class="card">
    <div class="card-title">Company Intelligence</div>
    <p style="color: var(--gray-700); margin-bottom: 12px; font-size: 14px;"><strong>About:</strong> {{ company_desc }}</p>
    {% if company_business_unit and company_business_unit != 'N/A' %}
      <p style="color: var(--gray-700); margin-bottom: 16px; font-size: 14px;"><strong>Business Unit:</strong> {{ company_business_unit }}</p>
    {% else %}
      <p style="color: var(--gray-700); margin-bottom: 16px; font-size: 14px;"><strong>Business Unit:</strong> <span style="font-style: italic; color: var(--gray-500);">Not specified in Job Description</span></p>
    {% endif %}

    <div class="company-info-grid" style="margin-bottom: 16px;">
      <div class="info-row">
        <span class="info-label">CEO</span>
        <span class="info-value">{{ company_ceo }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Industry</span>
        <span class="info-value">{{ company_industry }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Headquarters</span>
        <span class="info-value">{{ company_hq }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Employees</span>
        <span class="info-value">{{ company_employees }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Glassdoor Rating</span>
        <span class="info-value">
          {% if company_glassdoor_rating %}
            <span style="color: #16a34a; font-weight: 700;">&#9733; {{ company_glassdoor_rating }}</span>
            <span style="font-size: 11px; color: #64748b; font-weight: 400;">({{ company_glassdoor_reviews }})</span>
          {% else %}
            N/A
          {% endif %}
        </span>
      </div>
      <div class="info-row" style="grid-column: span 2;">
        <div style="display: flex; justify-content: space-between; align-items: baseline;">
            <span class="info-label">Market Cap</span>
            <span style="font-size: 11px; color: var(--gray-600); font-style: italic;">Source: {{ company_source }}</span>
        </div>
        <span class="info-value">{{ company_market_cap }}</span>
      </div>
    </div>
    <div class="two-col">
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Culture</strong>
        <ul class="styled-list">
          {% if company_culture %}
            {% for item in company_culture %}
              <li>{{ item }}</li>
            {% endfor %}
          {% else %}
            <li>No culture data available</li>
          {% endif %}
        </ul>
      </div>
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Recent News</strong>
        <ul class="styled-list">
          {% if company_news %}
            {% for item in company_news %}
              <li>{{ item }}</li>
            {% endfor %}
          {% else %}
            <li>No recent news available</li>
          {% endif %}
        </ul>
      </div>
    </div>
    {% if company_networking and company_networking != 'N/A' %}
      <div style="margin-top: 16px; padding: 12px; background: #eff6ff; border-radius: 8px; border-left: 4px solid #3b82f6;">
        <strong style="font-size: 14px; display: block; margin-bottom: 4px; color: #1e40af;">LinkedIn Networking Target</strong>
        <p style="font-size: 13px; color: #1e3a8a; margin: 0;">{{ company_networking }}</p>
      </div>
    {% endif %}

    {% if company_glassdoor_pros or company_glassdoor_cons %}
      <div style="margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
        <div style="padding: 10px; background: #f0fdf4; border-radius: 8px; border: 1px solid #dcfce3;">
          <strong style="font-size: 12px; color: #166534; display: block; margin-bottom: 4px;">Glassdoor Pros</strong>
          <ul style="margin: 0; padding-left: 16px; font-size: 12px; color: #14532d;">
            {% for pro in company_glassdoor_pros %}<li>{{ pro }}</li>{% endfor %}
          </ul>
        </div>
        <div style="padding: 10px; background: #fef2f2; border-radius: 8px; border: 1px solid #fecaca;">
          <strong style="font-size: 12px; color: #991b1b; display: block; margin-bottom: 4px;">Glassdoor Cons</strong>
          <ul style="margin: 0; padding-left: 16px; font-size: 12px; color: #7f1d1d;">
            {% for con in company_glassdoor_cons %}<li>{{ con }}</li>{% endfor %}
          </ul>
        </div>
      </div>
    {% endif %}

    {% if company_revenue_breakdown or company_org_chart %}
    <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--gray-200);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <strong style="font-size: 16px; color: var(--primary);">Corporate Structure & Revenue</strong>
        {% if edgar_link %}
        <a href="{{ edgar_link }}" target="_blank" style="text-decoration: none; display: flex; align-items: center; gap: 6px; background: #f8fafc; border: 1px solid #e5e7eb; padding: 5px 12px; border-radius: 6px; font-size: 12px; color: #374151; font-weight: 600;">
          Latest 10-K (SEC EDGAR)
        </a>
        {% endif %}
      </div>
      <div class="two-col">
        {% if company_revenue_breakdown %}
        <div>
          <strong style="font-size: 14px; display: block; margin-bottom: 8px; color: var(--gray-700);">Revenue Breakdown by Division</strong>
          <table style="width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid var(--gray-200); border-radius: 6px; overflow: hidden;">
            <thead style="background: var(--gray-100); border-bottom: 1px solid var(--gray-200); text-align: left;">
              <tr>
                <th style="padding: 8px 12px; font-weight: 600;">Division</th>
                <th style="padding: 8px 12px; font-weight: 600; text-align: right;">Revenue %</th>
              </tr>
            </thead>
            <tbody>
              {% for r in company_revenue_breakdown %}
              <tr style="border-bottom: 1px solid var(--gray-100);">
                <td style="padding: 8px 12px; color: var(--gray-700);">{{ r.get("division", "") }}</td>
                <td style="padding: 8px 12px; text-align: right; font-weight: 600; color: var(--success);">{{ r.get("revenue_percentage", "") }}</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
        {% else %}
        <div><p style='font-size: 13px; color: var(--gray-500); font-style: italic;'>Revenue breakdown not available.</p></div>
        {% endif %}

        {% if company_org_chart %}
        <div>
          <strong style="font-size: 14px; display: block; margin-bottom: 8px; color: var(--gray-700);">Organizational Hierarchy</strong>
          <div style="background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: 6px; padding: 12px; overflow-x: auto;">
            <div class="mermaid">
              {{ company_org_chart }}
            </div>
          </div>
        </div>
        {% else %}
        <div><p style='font-size: 13px; color: var(--gray-500); font-style: italic;'>Org chart not available.</p></div>
        {% endif %}
      </div>
    </div>
    {% endif %}
  </div>

  <!-- Skills -->
  <div class="card">
    <div class="card-title">Required Skills</div>
    <div>
      {% if required_skills %}
        {% for skill in required_skills %}
          <span class="badge">{{ skill }}</span>
        {% endfor %}
      {% else %}
        <span class="badge badge-warning">Not specified</span>
      {% endif %}
    </div>
  </div>

  <!-- Resume Tailoring & Skill Gaps -->
  {% if skill_gap %}
  <div class="card">
    <div class="card-title">Resume Tailoring & Skill Gaps</div>

    <div class="two-col">
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">ATS Keywords to Add</strong>
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px;">
          {% for kw in skill_gap.ats_keywords_to_add %}
            <span style="background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">+ {{ kw }}</span>
          {% endfor %}
        </div>

        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Suggested Bullet Points</strong>
        <ul class="styled-list" style="font-size: 13px;">
          {% for bullet in skill_gap.suggested_bullet_points %}
            <li>{{ bullet }}</li>
          {% endfor %}
        </ul>
      </div>

      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Priority Gaps to Bridge</strong>
        {% for gap in skill_gap.skill_gaps %}
          <div class="gap-item gap-priority-{{ gap.priority | lower }}">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="font-weight: 700; font-size: 13px; color: var(--gray-900);">{{ gap.missing_skill }}</span>
              <span style="font-size: 10px; font-weight: 800; text-transform: uppercase;">{{ gap.priority }} priority</span>
            </div>
            <p style="font-size: 12px; color: var(--gray-600); line-height: 1.4;">{{ gap.recommendation }}</p>
          </div>
        {% endfor %}
      </div>
    </div>
  </div>
  {% endif %}

  <!-- Responsibilities -->
  <div class="card">
    <div class="card-title">Key Responsibilities</div>
    <ul class="styled-list">
      {% if responsibilities %}
        {% for item in responsibilities %}
          <li>{{ item }}</li>
        {% endfor %}
      {% else %}
        <li>Not available</li>
      {% endif %}
    </ul>
  </div>

  <!-- Salary Intelligence -->
  <div class="card">
    <div class="card-title">Salary Intelligence</div>
    <div class="salary-grid">
      <div class="salary-stat">
        <div class="value">{{ salary_min }}</div>
        <div class="label">Minimum</div>
      </div>
      <div class="salary-stat">
        <div class="value">{{ salary_median }}</div>
        <div class="label">Median</div>
      </div>
      <div class="salary-stat">
        <div class="value">{{ salary_max }}</div>
        <div class="label">Maximum</div>
      </div>
    </div>
    {{ salary_chart_svg | safe }}
    <p style="color: var(--gray-600); font-size: 14px; margin-bottom: 4px;">
      <strong>Estimated Range:</strong> {{ salary_range }}
    </p>
    {% if salary_data_label %}
      <p style="color: #d97706; font-size: 13px; margin-bottom: 4px;">&#9888; {{ salary_data_label }}</p>
    {% endif %}
    <p style="color: var(--gray-600); font-size: 13px; margin-bottom: 4px;">
      Data confidence: {{ salary_confidence }}%
    </p>
    <div class="confidence-bar">
      <div class="confidence-fill" style="width: {{ salary_confidence }}%"></div>
    </div>
    <p style="color: var(--gray-600); font-size: 13px; margin-top: 8px;">
      Sources: {% if salary_sources %}{{ salary_sources | join(", ") }}{% else %}Market estimate only{% endif %}
    </p>
    {% if salary_breakdown %}
    <div style="margin-top: 16px;">
      <strong style="font-size: 14px;">Compensation Breakdown</strong>
      <table style="width: 100%; margin-top: 8px; border-collapse: collapse; font-size: 13px;">
        {% for k, v in salary_breakdown.items() %}
        <tr>
          <td style="padding: 6px 0; color: var(--gray-600); border-bottom: 1px solid var(--gray-100);">{{ k | replace("_", " ") | title }}</td>
          <td style="padding: 6px 0; font-weight: 500; border-bottom: 1px solid var(--gray-100);">{{ v }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
    {% endif %}
  </div>

  <!-- Interview Intelligence -->
  <div class="card">
    <div class="card-title">Interview Intelligence</div>
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
      <span class="badge difficulty-{{ interview_difficulty | lower }}" style="font-size: 13px; padding: 4px 14px;">
        Difficulty: {{ interview_difficulty }}
      </span>
      {% if not interview_data_warning and interview_source_count > 0 %}
        <span class="badge" style="background:#f0fdf4; color:#166534; border:1px solid #bbf7d0;">&#10003; Verified Data ({{ interview_source_count }} reviews)</span>
      {% else %}
        <span class="badge" style="background:#fef2f2; color:#991b1b; border:1px solid #fecaca;">&#9888; Estimated Guide</span>
      {% endif %}
    </div>
    <div class="confidence-bar" style="margin-bottom: 12px;">
      <div class="confidence-fill" style="width: {{ interview_confidence }}%; background: {% if interview_confidence > 70 %}#22c55e{% elif interview_confidence > 40 %}#eab308{% else %}#ef4444{% endif %};"></div>
    </div>
    {% if interview_data_warning %}
      <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;padding:10px 14px;margin-bottom:12px;font-size:13px;color:#92400e;">&#9888; {{ interview_source }}</div>
    {% else %}
      <p style="font-size:13px;color:var(--gray-600);margin-bottom:12px;">Source: {{ interview_source }}</p>
    {% endif %}

    {% if interview_overview %}
      <p style="color: var(--gray-700); font-size: 14px; margin-bottom: 16px;">{{ interview_overview }}</p>
    {% endif %}

    <div style="margin-bottom: 20px;">
      <strong style="font-size: 14px; display: block; margin-bottom: 10px;">Interview Process</strong>
      <div class="rounds-list">
        {% for r in interview_rounds %}
          <div class="round-item"><div class="round-num">{{ loop.index }}</div><span style="font-size: 14px;">{{ r }}</span></div>
        {% endfor %}
      </div>
    </div>

    {% if study_guide_sections %}
    <div style="margin-bottom: 32px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;">
      <div style="background: #f8fafc; padding: 16px 20px; border-bottom: 1px solid #e2e8f0;">
        <strong style="font-size: 16px; color: #1e293b;">Complete Interview Study Guide</strong>
      </div>
      <div style="padding: 24px 32px;">
        {% for sec in study_guide_sections %}
           <div style="margin-bottom: 32px; border-bottom: 1px solid #e2e8f0; padding-bottom: 24px;">
              <h3 style="color: #1e293b; font-size: 18px; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 2px solid #cbd5e1; display: inline-block; padding-bottom: 4px;">{{ sec.title }}</h3>
              {% for sub in sec.subsections %}
              <div style="margin-bottom: 24px;">
                  <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                      <div style="display: flex; align-items: center; gap: 12px;">
                          <h4 style="margin: 0; font-size: 15px; color: #0f172a;">{{ sub.title }}</h4>
                          <span style="background: {% if sub.importance == 'CRITICAL' %}#fef2f2{% elif sub.importance == 'HIGH' %}#fffbeb{% else %}#eff6ff{% endif %}; color: {% if sub.importance == 'CRITICAL' %}#991b1b{% elif sub.importance == 'HIGH' %}#92400e{% else %}#1e40af{% endif %}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">{{ sub.importance }}</span>
                      </div>
                      <div style="display: flex; gap: 6px;">
                          <button onclick="sendFeedback('{{ job_id }}', 'study_guide', 1, '{{ sub.title | escape_js }}', this)" style="border:1px solid #e2e8f0; background:white; cursor:pointer; padding:4px 8px; border-radius:4px; font-size:12px; color:#475569;">&#128077;</button>
                          <button onclick="sendFeedback('{{ job_id }}', 'study_guide', -1, '{{ sub.title | escape_js }}', this)" style="border:1px solid #e2e8f0; background:white; cursor:pointer; padding:4px 8px; border-radius:4px; font-size:12px; color:#475569;">&#128078;</button>
                      </div>
                  </div>
                  <ul style="margin: 0; padding-left: 20px; font-size: 14px; color: #475569;">
                      {% for bullet in sub.bullet_points %}
                        <li style="margin-bottom: 8px; line-height: 1.6;">{{ bullet }}</li>
                      {% endfor %}
                  </ul>
                  <div style="margin-top: 12px; font-size: 12px; color: #64748b; font-style: italic; background: #f8fafc; padding: 8px 12px; border-left: 3px solid #cbd5e1;">
                      <strong>Source:</strong> {{ sub.jd_justification }}
                  </div>
              </div>
              {% endfor %}
          </div>
        {% endfor %}
      </div>
    </div>
    {% endif %}

    <div class="two-col">
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Technical Questions</strong>
        <ul class="styled-list">
          {% if tech_questions %}
            {% for item in tech_questions %}
              <li>{{ item }}</li>
            {% endfor %}
          {% else %}
            <li>Not available</li>
          {% endif %}
        </ul>
      </div>
      <div>
        <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Behavioral Questions</strong>
        <ul class="styled-list">
          {% if behavioral_questions %}
            {% for item in behavioral_questions %}
              <li>{{ item }}</li>
            {% endfor %}
          {% else %}
            <li>Not available</li>
          {% endif %}
        </ul>
      </div>
    </div>

    <div style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--gray-100);">
      <strong style="font-size: 14px; display: block; margin-bottom: 8px;">Preparation Tips</strong>
      <ul class="styled-list">
        {% if interview_tips %}
            {% for item in interview_tips %}
              <li>{{ item }}</li>
            {% endfor %}
          {% else %}
            <li>Not available</li>
          {% endif %}
      </ul>
      {% if interview_platforms %}
        <p style="font-size: 12px; color: var(--gray-600); margin-top: 16px; font-style: italic;">Analyzed candidate insights from: {{ interview_platforms | join(", ") }}</p>
      {% endif %}
    </div>
  </div>

  <!-- Metadata -->
  <div class="card" style="background: var(--gray-50); border-style: dashed;">
    <div class="card-title" style="font-size: 14px; color: var(--gray-600);">&#128203; Analysis Metadata</div>
    <div class="company-info-grid">
      <div class="info-row">
        <span class="info-label">Job ID</span>
        <span class="info-value" style="font-family: monospace; font-size: 12px;">{{ job_id or "N/A" }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Generated</span>
        <span class="info-value">{{ generated_at }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Salary Confidence</span>
        <span class="info-value">{{ salary_confidence }}% &#8212; {{ salary_data_label or "Market estimate" }}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Data Sources</span>
        <span class="info-value">{% if salary_sources %}{{ salary_sources | join(", ") }}{% else %}Market estimate{% endif %}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Interview Data</span>
        <span class="info-value">{% if interview_data_warning %}AI-generated guide{% else %}RAG corpus{% endif %}</span>
      </div>
      <div class="info-row">
        <span class="info-label">Company Source</span>
        <span class="info-value">{{ company_source }}</span>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <div class="report-footer">
    <p>Generated by <strong>HireScope</strong> on {{ generated_at }}</p>
    <p style="margin-top: 4px; font-size: 12px;">
      AI-powered job intelligence. Salary from DOL H1B disclosures + Gemini. Company from Wikipedia + Gemini. Interviews from corpus + Gemini.
    </p>
  </div>

</div>
<script>
function sendFeedback(jobId, section, value, sourceText, btnElem) {
  fetch(`/api/jobs/${jobId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section: section, feedback_type: value, source_text: sourceText })
  }).then(res => {
    if(res.ok) {
       const originalText = btnElem.innerText;
       const originalBg = btnElem.style.background;
       btnElem.style.background = value === 1 ? '#dcfce3' : '#fee2e2';
       btnElem.innerText = value === 1 ? '\u2705' : '\u274c';
       btnElem.disabled = true;
       setTimeout(() => {
           btnElem.style.background = originalBg;
           btnElem.innerText = originalText;
           btnElem.disabled = false;
       }, 2000);
    }
  }).catch(err => console.error(err));
}
</script>
</body>
</html>"""


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
    compatibility_intel: dict = None,
    skill_gap_intel: dict = None,
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
        "company_glassdoor_rating": company_intel.get("glassdoor_rating"),
        "company_glassdoor_reviews": company_intel.get("glassdoor_review_count"),
        "company_glassdoor_pros": company_intel.get("glassdoor_pros", []),
        "company_glassdoor_cons": company_intel.get("glassdoor_cons", []),
        "company_glassdoor_url": company_intel.get("glassdoor_url"),
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

        "compatibility": compatibility_intel or {},
        "skill_gap": skill_gap_intel or {},

        "generated_at": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
    }

    try:
        template_source = _load_template_source()
        template = template_env.from_string(template_source)
        html = template.render(**context)
        logger.info(f"Generated HTML report for '{job_title}' at '{company}' ({len(html)} chars)")
        return html
    except Exception as e:
        logger.error(f"Template rendering failed: {e}", exc_info=True)
        return f"<h1>Error Generating Report</h1><p>{str(e)}</p>"
