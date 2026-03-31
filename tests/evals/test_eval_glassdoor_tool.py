import json
import os
import pytest
from utils.glassdoor import get_glassdoor_data

def load_benchmark_data():
    file_path = os.path.join(os.path.dirname(__file__), 'benchmark_data.json')
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data["companies"]

@pytest.mark.asyncio
@pytest.mark.parametrize("company_info", load_benchmark_data())
async def test_get_glassdoor_data_benchmark(company_info):
    """
    Live Benchmark: Evaluates the Glassdoor data extraction against a dataset of diverse companies.
    Validates structural LLM compliance and accurate handling of unknown edges cases.
    """
    company_name = company_info["name"]
    expected_valid = company_info["expected_glassdoor_valid"] == "True"

    # Run live extraction against Gemini
    result = await get_glassdoor_data(company_name)

    # Core JSON checks
    assert result is not None, f"Expected data dictionary for {company_name}"
    expected_keys = {"rating", "review_count", "pros", "cons", "url"}
    assert all(k in result for k in expected_keys), f"Missing requested schema keys for {company_name}"

    # Dynamic benchmark logic based on "known" vs "unknown" company matrix
    if expected_valid:
        # Check numeric bounds and types
        assert isinstance(result["rating"], (int, float)), f"Rating must be a number for {company_name}"
        assert 0.0 < result["rating"] <= 5.0, f"Rating {result['rating']} is out of plausible bounds for {company_name}"

        # Check string attributes
        assert isinstance(result["review_count"], str), "Review count should be a formatted string (e.g. '15k+')"
        assert len(result["review_count"]) > 0, f"Valid company '{company_name}' should have a review count string"

        assert isinstance(result["url"], str)
        assert result["url"] == "N/A" or "glassdoor" in result["url"].lower(), "URL must point to Glassdoor or cleanly fallback to N/A"

        # Array checking relaxes rigid count assertions but verifies type
        assert isinstance(result["pros"], list)
        assert isinstance(result["cons"], list)

    else:
        # LLM should gracefully default values for an entirely fake/unknown company
        assert result["rating"] == 0, f"Fake company '{company_name}' should have a 0 rating"
        assert result["review_count"] in ["N/A", "0", ""], f"Fake company '{company_name}' should not hallucinate a review count"
