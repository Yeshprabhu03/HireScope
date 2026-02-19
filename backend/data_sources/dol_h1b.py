"""
DOL H1B data source: loads and queries H-1B Disclosure Data from DOL CSV files.
Data source: https://www.dol.gov/agencies/eta/foreign-labor/performance
"""
import logging
import os
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

_h1b_df: Optional[pd.DataFrame] = None

MOCK_SALARY_DATA = {
    "min": 150000,
    "max": 250000,
    "median": 195000,
    "mean": 197500,
    "count": 47,
    "source": "DOL H1B Disclosure Data (mock)",
    "records": [
        {"employer": "Google LLC", "job_title": "Senior Software Engineer", "wage_from": 180000, "wage_to": 220000, "city": "Mountain View"},
        {"employer": "Google LLC", "job_title": "Software Engineer III", "wage_from": 165000, "wage_to": 200000, "city": "Sunnyvale"},
        {"employer": "Google LLC", "job_title": "Senior SWE", "wage_from": 190000, "wage_to": 250000, "city": "New York"},
    ],
}


def load_h1b_data(csv_path: str) -> Optional[pd.DataFrame]:
    """
    Load H1B disclosure data from CSV.
    Expected columns: EMPLOYER_NAME, JOB_TITLE, WAGE_RATE_OF_PAY_FROM,
                      WAGE_RATE_OF_PAY_TO, WORKSITE_CITY, WORKSITE_STATE
    """
    global _h1b_df
    if _h1b_df is not None:
        return _h1b_df

    if not os.path.exists(csv_path):
        logger.warning(f"H1B CSV not found at {csv_path}. Salary data will use mock/estimates.")
        return None

    try:
        logger.info(f"Loading H1B data from {csv_path}")
        df = pd.read_csv(csv_path, low_memory=False)
        df.columns = [c.upper().strip() for c in df.columns]

        # Normalize wage columns to numeric
        for col in ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO"]:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r"[,$]", "", regex=True),
                    errors="coerce",
                )

        # Annualize wages (assume hourly if < 500, weekly if < 10000, else annual)
        for col in ["WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda w: w * 2080 if pd.notna(w) and w < 500
                    else (w * 52 if pd.notna(w) and w < 10000 else w)
                )

        _h1b_df = df
        logger.info(f"Loaded {len(df)} H1B records")
        return df

    except Exception as e:
        logger.error(f"Failed to load H1B data: {e}", exc_info=True)
        return None


def _fuzzy_match(series: pd.Series, keyword: str, threshold: float = 0.5) -> pd.Series:
    """Simple fuzzy match: check if all words in keyword appear in the value."""
    keyword_lower = keyword.lower()
    words = [w for w in keyword_lower.split() if len(w) > 2]
    if not words:
        return series.str.lower().str.contains(keyword_lower, na=False)
    mask = pd.Series([True] * len(series), index=series.index)
    for word in words:
        mask &= series.str.lower().str.contains(word, na=False, regex=False)
    return mask


def get_salary_data(
    df: Optional[pd.DataFrame],
    job_title: str,
    company: str,
    location: str,
) -> dict:
    """
    Query H1B data to return salary statistics for a given role.
    Falls back to mock data if df is None or no records found.
    """
    if df is None:
        logger.info("No H1B dataframe available, using mock salary data")
        return MOCK_SALARY_DATA

    try:
        # Filter by job title (fuzzy)
        title_mask = _fuzzy_match(df.get("JOB_TITLE", pd.Series(dtype=str)), job_title)
        filtered = df[title_mask].copy()

        if len(filtered) == 0:
            logger.info(f"No H1B records found for job_title='{job_title}', using mock data")
            return MOCK_SALARY_DATA

        # Further filter by company if possible
        if company and company.lower() != "unknown":
            company_mask = _fuzzy_match(
                filtered.get("EMPLOYER_NAME", pd.Series(dtype=str)), company
            )
            company_filtered = filtered[company_mask]
            if len(company_filtered) > 0:
                filtered = company_filtered

        # Use wage_from as base salary
        wage_col = "WAGE_RATE_OF_PAY_FROM"
        if wage_col not in filtered.columns:
            return MOCK_SALARY_DATA

        wages = filtered[wage_col].dropna()
        wages = wages[(wages >= 30000) & (wages <= 1000000)]  # Sanity filter

        if len(wages) == 0:
            return MOCK_SALARY_DATA

        # Build records sample
        sample_cols = [
            c for c in ["EMPLOYER_NAME", "JOB_TITLE", "WAGE_RATE_OF_PAY_FROM",
                         "WAGE_RATE_OF_PAY_TO", "WORKSITE_CITY"]
            if c in filtered.columns
        ]
        records = filtered[sample_cols].head(5).to_dict(orient="records")

        result = {
            "min": int(wages.min()),
            "max": int(wages.max()),
            "median": int(wages.median()),
            "mean": int(wages.mean()),
            "p25": int(wages.quantile(0.25)),
            "p75": int(wages.quantile(0.75)),
            "count": len(wages),
            "source": "DOL H1B Disclosure Data",
            "records": records,
        }
        logger.info(
            f"H1B salary data: median=${result['median']:,} (n={result['count']}) "
            f"for '{job_title}' at '{company}'"
        )
        return result

    except Exception as e:
        logger.error(f"Error querying H1B data: {e}", exc_info=True)
        return MOCK_SALARY_DATA
