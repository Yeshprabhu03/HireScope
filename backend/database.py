import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, SQLModel, create_engine, select, Session, Column, JSON, text
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from config import settings

logger = logging.getLogger(__name__)

# Update URL to use asyncpg
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("sqlite:///") and "+aiosqlite" not in db_url:
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(db_url, echo=False, future=True)

async def init_db():
    """Initialize the database and create tables."""
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all) # Dangerous, only for dev reset
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database initialized with SQLModel schemas.")

async def get_session() -> SQLModelAsyncSession:
    async_session = sessionmaker(
        engine, class_=SQLModelAsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

# --- Models ---

class JobPosting(SQLModel, table=True):
    __tablename__ = "job_postings"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_url: str = Field(index=True, unique=True)
    company: Optional[str] = None
    job_title: Optional[str] = None
    parsed_jd: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    raw_html: Optional[str] = None
    scraped_at: datetime = Field(default_factory=datetime.now)
    first_seen: datetime = Field(default_factory=datetime.now)

class CompanySnapshot(SQLModel, table=True):
    __tablename__ = "company_snapshots"
    company: str = Field(primary_key=True)
    snapshot_date: datetime = Field(default_factory=datetime.now)
    data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

class SalaryObservation(SQLModel, table=True):
    __tablename__ = "salary_observations"
    job_url: str = Field(primary_key=True)
    company: str = Field(index=True)
    job_title: str = Field(index=True)
    location: Optional[str] = Field(default=None, index=True)
    seniority: Optional[str] = None
    jd_salary_mentioned: Optional[str] = None
    jd_salary_min: Optional[float] = None
    jd_salary_max: Optional[float] = None
    h1b_median: Optional[float] = None
    observed_at: datetime = Field(default_factory=datetime.now)
    confidence_score: float = Field(default=0.0)

class InterviewExperience(SQLModel, table=True):
    __tablename__ = "interview_corpus"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company: str = Field(index=True)
    role: Optional[str] = None
    role_category: Optional[str] = Field(default=None, index=True)
    experience_text: str
    scraped_at: datetime = Field(default_factory=datetime.now)
    indexed_in_chromadb: bool = Field(default=True)

class UserFeedback(SQLModel, table=True):
    __tablename__ = "user_feedback"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: str = Field(index=True)
    section: str
    feedback_type: int  # 1 for upvote, -1 for downvote
    source_text: str
    created_at: datetime = Field(default_factory=datetime.now)

# --- Service Functions (Async) ---

async def get_job_posting(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached job posting by its UUID."""
    async with SQLModelAsyncSession(engine) as session:
        try:
            uid = UUID(job_id)
        except ValueError:
            # Maybe it's a URL? Let's check by URL as fallback
            statement = select(JobPosting).where(JobPosting.job_url == job_id)
            results = await session.execute(statement)
            job = results.scalar_one_or_none()
            return job.model_dump() if job else None

        statement = select(JobPosting).where(JobPosting.id == uid)
        results = await session.execute(statement)
        job = results.scalar_one_or_none()
        if job:
            return job.model_dump()
        return None

async def save_job_posting(job_id: str, job_url: str, company: str, job_title: str, parsed_jd: dict, raw_html: str):
    """Insert or update a job posting in the database (upsert by URL)."""
    async with SQLModelAsyncSession(engine) as session:
        uid = UUID(job_id)

        # First try to find by primary key (job_id)
        statement = select(JobPosting).where(JobPosting.id == uid)
        results = await session.execute(statement)
        job = results.scalar_one_or_none()

        # If not found by id, check by URL (handles re-analysis of same job)
        if not job:
            url_statement = select(JobPosting).where(JobPosting.job_url == job_url)
            url_results = await session.execute(url_statement)
            job = url_results.scalar_one_or_none()

        if job:
            # Update the existing record
            job.company = company
            job.job_title = job_title
            job.parsed_jd = parsed_jd
            job.raw_html = raw_html
            job.scraped_at = datetime.now()
        else:
            job = JobPosting(
                id=uid,
                job_url=job_url,
                company=company,
                job_title=job_title,
                parsed_jd=parsed_jd,
                raw_html=raw_html
            )
            session.add(job)

        await session.commit()

async def get_company_snapshot(company: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached company snapshot if it exists."""
    async with SQLModelAsyncSession(engine) as session:
        statement = select(CompanySnapshot).where(CompanySnapshot.company == company)
        results = await session.execute(statement)
        snap = results.scalar_one_or_none()
        if snap:
            return snap.model_dump()
        return None

async def save_company_snapshot(company: str, data: dict):
    """Insert or update a company intelligence snapshot."""
    async with SQLModelAsyncSession(engine) as session:
        statement = select(CompanySnapshot).where(CompanySnapshot.company == company)
        results = await session.execute(statement)
        snap = results.scalar_one_or_none()

        if snap:
            snap.data = data
            snap.snapshot_date = datetime.now()
        else:
            snap = CompanySnapshot(company=company, data=data)
            session.add(snap)

        await session.commit()

# --- Salary Logic ---
import re

def extract_salary_numbers(salary_string: str) -> tuple[Optional[int], Optional[int]]:
    if not salary_string or not isinstance(salary_string, str):
        return None, None
    salary_string = salary_string.lower()
    numbers = []
    pattern = r'\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+(?:\.\d+)?)\s*(k)?'
    matches = re.finditer(pattern, salary_string)
    for match in matches:
        num_str = match.group(1).replace(',', '')
        try:
            val = float(num_str)
            if match.group(2) == 'k' or val < 1000:
                val *= 1000
            if val > 30000:
                numbers.append(int(val))
        except ValueError:
            continue
    if not numbers:
        return None, None
    elif len(numbers) == 1:
        return numbers[0], numbers[0]
    else:
        numbers.sort()
        return numbers[0], numbers[-1]

async def save_salary_observation(job_url: str, company: str, job_title: str, location: str, seniority: str, jd_salary_mentioned: str, h1b_median: float = None, confidence_score: float = 0.0):
    min_sal, max_sal = extract_salary_numbers(jd_salary_mentioned)
    if not min_sal and not max_sal:
        return

    async with SQLModelAsyncSession(engine) as session:
        statement = select(SalaryObservation).where(SalaryObservation.job_url == job_url)
        results = await session.execute(statement)
        obs = results.scalar_one_or_none()

        if obs:
            obs.company = company
            obs.job_title = job_title
            obs.location = location
            obs.seniority = seniority
            obs.jd_salary_mentioned = jd_salary_mentioned
            obs.jd_salary_min = min_sal
            obs.jd_salary_max = max_sal
            obs.h1b_median = h1b_median
            obs.observed_at = datetime.now()
            obs.confidence_score = confidence_score
        else:
            obs = SalaryObservation(
                job_url=job_url,
                company=company,
                job_title=job_title,
                location=location,
                seniority=seniority,
                jd_salary_mentioned=jd_salary_mentioned,
                jd_salary_min=min_sal,
                jd_salary_max=max_sal,
                h1b_median=h1b_median,
                confidence_score=confidence_score
            )
            session.add(obs)
        await session.commit()

async def get_historical_salary(company: str, job_title: str, location: str) -> Optional[Dict[str, Any]]:
    """Retrieve robust historical average using PostgreSQL-safe logic."""
    title_pattern = f"%{job_title}%"
    async with SQLModelAsyncSession(engine) as session:
        # Using raw SQL for the aggregate to handle the title pattern match easily
        # PostgreSQL syntax
        from sqlalchemy import func
        statement = select(
            func.count(SalaryObservation.job_url).label("obs_count"),
            func.avg(SalaryObservation.jd_salary_min).label("avg_min"),
            func.avg(SalaryObservation.jd_salary_max).label("avg_max")
        ).where(
            SalaryObservation.company == company,
            SalaryObservation.job_title.like(title_pattern),
            SalaryObservation.jd_salary_min != None,
            SalaryObservation.observed_at > text("now() - interval '2 years'")
        )

        results = await session.execute(statement)
        row = results.first()

        if row and row.obs_count >= 5:
            return {
                "count": row.obs_count,
                "avg_min": int(row.avg_min) if row.avg_min else None,
                "avg_max": int(row.avg_max) if row.avg_max else None
            }
        return None

async def save_interview_experiences(company: str, role: str, role_category: str, experiences: List[str]) -> List[str]:
    async with SQLModelAsyncSession(engine) as session:
        inserted_ids = []
        for exp in experiences:
            obj = InterviewExperience(
                company=company,
                role=role,
                role_category=role_category,
                experience_text=exp
            )
            session.add(obj)
            await session.flush()
            inserted_ids.append(str(obj.id))
        await session.commit()
        return inserted_ids

async def save_user_feedback(job_id: str, section: str, feedback_type: int, source_text: str):
    async with SQLModelAsyncSession(engine) as session:
        feedback = UserFeedback(
            job_id=job_id,
            section=section,
            feedback_type=feedback_type,
            source_text=source_text
        )
        session.add(feedback)
        await session.commit()
