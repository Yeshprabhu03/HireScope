import json
import os
import pytest
from data_sources.company_intel import fetch_company_intel

def load_benchmark_data():
    file_path = os.path.join(os.path.dirname(__file__), 'benchmark_data.json')
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data["companies"]

@pytest.mark.asyncio
@pytest.mark.parametrize("company_info", load_benchmark_data())
async def test_fetch_company_intel_benchmark(company_info):
    """
    Live Benchmark: Evaluates the Gemini agent's ability to structurally extract,
    generate, and map internal organizational hierarchies across diverse domains.
    """
    company_name = company_info["name"]
    expected_public = company_info["expected_public"] == "True"

    # Run the live extraction. The LLM handles the deep dive data, including generating the org chart.
    intel = await fetch_company_intel(
        company=company_name,
        role=company_info["test_role"],
        sub_team=company_info["test_sub_team"],
        use_mock=False
    )

    # Base Assertions
    assert intel is not None, f"Expected intel dictionary for {company_name}"
    assert intel.get("name") == company_name, "API should return matching company name"

    # 1. Mermaid Generation Benchmark Check
    mermaid_str = intel.get("org_chart_mermaid", "")
    assert isinstance(mermaid_str, str), "Mermaid output must be a string type"

    if company_info["type"] != "Unknown Small Business":
        assert mermaid_str != "", f"LLM should generate an org chart string for {company_name}"
        assert mermaid_str.startswith("graph ") or mermaid_str.startswith("flowchart "), \
            f"Mermaid string must start with valid syntax rules. Got: {mermaid_str[:20]}..."
        assert "```" not in mermaid_str, f"Mermaid string hallucinated markdown blocks on {company_name}"

    # 2. Financials Benchmark Check
    market_cap = intel.get("market_cap")
    if expected_public:
        assert market_cap != "N/A", f"{company_name} is publicly traded, market cap must be resolved"
        assert market_cap.startswith("$"), f"Market cap should format as US currency string, got {market_cap}"
    else:
        # LLM + Yahoo Finance shouldn't assign random market caps to private / fake companies
        assert market_cap in ["N/A", "Not Listed / Private"], f"Private/Unknown {company_name} shouldn't have market cap math"

    # 3. Structural Revenue Data Check
    breakdown = intel.get("revenue_breakdown", [])
    assert isinstance(breakdown, list), "Revenue breakdown must map to a list array"
    if expected_public:
         # Public giants are almost guaranteed to return estimates for divisions
         assert len(breakdown) > 0, f"Expected estimated revenue division array for public {company_name}"
         if len(breakdown) > 0:
             first_div = breakdown[0]
             assert "division" in first_div and "revenue_percentage" in first_div, "Revenue item schema broken"
