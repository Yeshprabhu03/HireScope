import sqlite3
import json
import logging
import os
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(settings.DATA_DIR, "hirescope.db")

def get_connection():
    """Create a database connection and enforce schema creation if missing."""
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _initialize_schema(conn)
    return conn

def _initialize_schema(conn):
    """Create the initial Phase 1 tables if they do not exist."""
    cursor = conn.cursor()
    
    # 1. Job Postings Table (Historical JD Database & Deduplication)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            job_url TEXT PRIMARY KEY,
            company TEXT,
            job_title TEXT,
            parsed_jd TEXT, -- JSON payload of the entire parsed JD
            raw_html TEXT,
            scraped_at TIMESTAMP,
            first_seen TIMESTAMP
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_company_title ON job_postings(company, job_title)")

    # 2. Company Intelligence Snapshots (Wikipedia Cache)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_snapshots (
            company TEXT PRIMARY KEY,
            snapshot_date TIMESTAMP,
            data TEXT -- JSON payload from company intel
        )
    """)
    
    # 3. Salary Observations (Continuous Learning Pipeline)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salary_observations (
            job_url TEXT PRIMARY KEY,
            company TEXT,
            job_title TEXT,
            location TEXT,
            seniority TEXT,
            jd_salary_mentioned TEXT,
            jd_salary_min NUMERIC,
            jd_salary_max NUMERIC,
            h1b_median NUMERIC,
            observed_at TIMESTAMP,
            confidence_score NUMERIC
        )
    """)
    # 4. Interview Corpus (On-Demand Scraping)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interview_corpus (
            id TEXT PRIMARY KEY,
            company TEXT,
            role TEXT,
            role_category TEXT,
            experience_text TEXT,
            scraped_at TIMESTAMP,
            indexed_in_chromadb BOOLEAN
        )
    """)
    
    # 5. User Feedback (Continuous Learning)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_feedback (
            id TEXT PRIMARY KEY,
            job_id TEXT,
            section TEXT,
            feedback_type INTEGER,
            source_text TEXT,
            created_at TIMESTAMP
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_salary_lookup ON salary_observations(company, job_title, location)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_interview_lookup ON interview_corpus(company, role_category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_job ON user_feedback(job_id)")
    
    conn.commit()

# --- Job Postings Functions ---

def get_job_passing(job_url: str):
    """Retrieve a cached job posting if it exists."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_postings WHERE job_url = ?", (job_url,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["parsed_jd"] = json.loads(data["parsed_jd"]) if data["parsed_jd"] else None
            return data
        return None

def save_job_posting(job_url: str, company: str, job_title: str, parsed_jd: dict, raw_html: str):
    """Insert or update a job posting in the database."""
    now = datetime.now().isoformat()
    parsed_json = json.dumps(parsed_jd)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Check if exists to preserve first_seen
        cursor.execute("SELECT first_seen FROM job_postings WHERE job_url = ?", (job_url,))
        row = cursor.fetchone()
        first_seen = row["first_seen"] if row else now
        
        cursor.execute("""
            INSERT INTO job_postings (job_url, company, job_title, parsed_jd, raw_html, scraped_at, first_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_url) DO UPDATE SET 
                company=excluded.company,
                job_title=excluded.job_title,
                parsed_jd=excluded.parsed_jd,
                raw_html=excluded.raw_html,
                scraped_at=excluded.scraped_at;
        """, (job_url, company, job_title, parsed_json, raw_html, now, first_seen))
        conn.commit()

# --- Company Intelligence Functions ---

def get_company_snapshot(company: str):
    """Retrieve a cached company snapshot if it exists."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM company_snapshots WHERE company = ?", (company,))
        row = cursor.fetchone()
        if row:
            data = dict(row)
            data["data"] = json.loads(data["data"]) if data["data"] else None
            return data
        return None

def save_company_snapshot(company: str, data: dict):
    """Insert or update a company intelligence snapshot."""
    now = datetime.now().isoformat()
    data_json = json.dumps(data)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO company_snapshots (company, snapshot_date, data)
            VALUES (?, ?, ?)
            ON CONFLICT(company) DO UPDATE SET 
                snapshot_date=excluded.snapshot_date,
                data=excluded.data;
        """, (company, now, data_json))
        conn.commit()

# --- Salary Intelligence Functions ---

import re

def extract_salary_numbers(salary_string: str) -> tuple[int|None, int|None]:
    """
    Extracts minimum and maximum salary integers from a string.
    Example: '150k - 200,000 USD' -> (150000, 200000)
    """
    if not salary_string or not isinstance(salary_string, str):
        return None, None
        
    salary_string = salary_string.lower()
    
    # Extract all numbers, handling commas and 'k' multipliers
    numbers = []
    # Pattern looks for numbers with optional commas, possibly followed by 'k'
    pattern = r'\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+(?:\.\d+)?)\s*(k)?'
    matches = re.finditer(pattern, salary_string)
    
    for match in matches:
        num_str = match.group(1).replace(',', '')
        try:
            val = float(num_str)
            # If it has a 'k' or is too small to be a full salary, multiply
            if match.group(2) == 'k' or val < 1000:
                val *= 1000
            
            # Filter out hourly rates or tiny numbers
            if val > 30000:
                numbers.append(int(val))
        except ValueError:
            continue
            
    if not numbers:
        return None, None
    elif len(numbers) == 1:
        return numbers[0], numbers[0]
    else:
        # Sort and take the lowest as min, highest as max to handle weird ranges
        numbers.sort()
        return numbers[0], numbers[-1]

def save_salary_observation(job_url: str, company: str, job_title: str, location: str, seniority: str, jd_salary_mentioned: str, h1b_median: float = None, confidence_score: float = 0.0):
    """Parse JD salary text and insert observational record."""
    min_sal, max_sal = extract_salary_numbers(jd_salary_mentioned)
    now = datetime.now().isoformat()
    
    # Only store if we found actual numbers to learn from
    if not min_sal and not max_sal:
        return
        
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO salary_observations (job_url, company, job_title, location, seniority, jd_salary_mentioned, jd_salary_min, jd_salary_max, h1b_median, observed_at, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_url) DO UPDATE SET 
                company=excluded.company,
                job_title=excluded.job_title,
                location=excluded.location,
                seniority=excluded.seniority,
                jd_salary_mentioned=excluded.jd_salary_mentioned,
                jd_salary_min=excluded.jd_salary_min,
                jd_salary_max=excluded.jd_salary_max,
                h1b_median=excluded.h1b_median,
                observed_at=excluded.observed_at,
                confidence_score=excluded.confidence_score;
        """, (job_url, company, job_title, location, seniority, jd_salary_mentioned, min_sal, max_sal, h1b_median, now, confidence_score))
        conn.commit()

def get_historical_salary(company: str, job_title: str, location: str) -> dict:
    """Retrieve robust historical average if enough observations exist."""
    # Build a permissive title match (e.g. "Software Engineer" matches "Senior Software Engineer")
    # For SQLite we use basic LIKE
    title_pattern = f"%{job_title}%"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Look back up to 2 years
        cursor.execute("""
            SELECT 
                COUNT(*) as obs_count, 
                AVG(jd_salary_min) as avg_min, 
                AVG(jd_salary_max) as avg_max
            FROM salary_observations
            WHERE company = ? 
              AND job_title LIKE ? 
              AND jd_salary_min IS NOT NULL
              AND datetime(observed_at) > datetime('now', '-2 years')
        """, (company, title_pattern))
        
        row = cursor.fetchone()
        
        if row and row['obs_count'] >= 5:
            return {
                "count": row['obs_count'],
                "avg_min": int(row['avg_min']) if row['avg_min'] else None,
                "avg_max": int(row['avg_max']) if row['avg_max'] else None
            }
        return None

# --- Interview Corpus Functions ---

import uuid

def save_interview_experiences(company: str, role: str, role_category: str, experiences: list[str]) -> list[str]:
    """Bulk insert new interview experiences into SQLite."""
    now = datetime.now().isoformat()
    inserted_ids = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for exp in experiences:
            exp_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO interview_corpus (id, company, role, role_category, experience_text, scraped_at, indexed_in_chromadb)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (exp_id, company, role, role_category, exp, now, True))
            inserted_ids.append(exp_id)
        conn.commit()
        
    return inserted_ids

# --- User Feedback Functions ---

def save_user_feedback(job_id: str, section: str, feedback_type: int, source_text: str):
    """Log user thumbs-up (1) or thumbs-down (-1) feedback."""
    now = datetime.now().isoformat()
    feedback_id = str(uuid.uuid4())
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_feedback (id, job_id, section, feedback_type, source_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (feedback_id, job_id, section, feedback_type, source_text, now))
        conn.commit()
