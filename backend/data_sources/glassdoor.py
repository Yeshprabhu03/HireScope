"""
Glassdoor cache: reads manually-scraped interview JSON files from corpus directory.
"""
import json
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def load_interview_corpus(corpus_dir: str) -> List[dict]:
    """Load all interview JSON files from the corpus directory."""
    interviews = []
    if not os.path.exists(corpus_dir):
        logger.warning(f"Interview corpus directory not found: {corpus_dir}")
        return interviews

    for filename in os.listdir(corpus_dir):
        if filename.endswith(".json"):
            filepath = os.path.join(corpus_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        interviews.extend(data)
                    else:
                        interviews.append(data)
            except Exception as e:
                logger.warning(f"Failed to load {filepath}: {e}")

    logger.info(f"Loaded {len(interviews)} interview records from corpus")
    return interviews


def get_interviews_for_company(
    corpus_dir: str,
    company: str,
    role: Optional[str] = None,
    limit: int = 10,
) -> List[dict]:
    """Filter interview records by company and optionally by role."""
    interviews = load_interview_corpus(corpus_dir)
    company_lower = company.lower()

    filtered = [
        i for i in interviews
        if company_lower in i.get("company", "").lower()
    ]

    if role and filtered:
        role_lower = role.lower().split()[0]  # Use first word of role
        role_filtered = [
            i for i in filtered
            if role_lower in i.get("role", "").lower()
        ]
        if role_filtered:
            filtered = role_filtered

    return filtered[:limit]
