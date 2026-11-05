"""
Shared Pydantic Schemas across all Multi-Agent microservices.
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    FIND_JOBS = "find_jobs"
    BUILD_RESUME = "build_resume"
    APPLY_JOB = "apply_job"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobSpec(BaseModel):
    """Canonical Job Specification returned by Scout and passed across agents."""
    id: str = Field(description="Unique job identifier")
    title: str = Field(description="Job title/role")
    company: str = Field(description="Company or employer name")
    location: str = Field(description="Job location or Remote")
    url: str = Field(description="Direct URL to view or apply")
    source: str = Field(default="web", description="Source board: naukri, linkedin, direct")
    salary: Optional[str] = Field(default=None, description="Salary bracket if disclosed")
    experience: Optional[str] = Field(default=None, description="Required experience range")
    description_snippet: Optional[str] = Field(default=None, description="Brief description snippet")
    match_score: Optional[int] = Field(default=None, description="0-100 relevance match percentage")
    matched_skills: List[str] = Field(default_factory=list, description="Candidate skills that match")
    missing_skills: List[str] = Field(default_factory=list, description="Required skills candidate lacks")
    match_summary: Optional[str] = Field(default=None, description="1-sentence LLM reasoning for the score")
    posted_date: Optional[str] = Field(default=None, description="Posting date or age if known")


class ScoutTaskPayload(BaseModel):
    """Input payload for Scout Agent."""
    role: str = Field(description="Target job title or keywords")
    location: str = Field(default="India", description="Target city or country")
    cities: List[str] = Field(default_factory=list, description="Specific cities to target")
    limit: int = Field(default=10, description="Max jobs to return")
    resume_text: Optional[str] = Field(default=None, description="Raw resume text for skill extraction")


class ScoutTaskRequest(BaseModel):
    """A2A Task Request from Manager to Scout."""
    task_id: str
    task_type: TaskType = TaskType.FIND_JOBS
    payload: ScoutTaskPayload


class ScoutTaskResult(BaseModel):
    """Result data produced by Scout."""
    total_found: int = 0
    returned_count: int = 0
    jobs: List[JobSpec] = Field(default_factory=list)


class ScoutTaskResponse(BaseModel):
    """A2A Task Response from Scout to Manager."""
    task_id: str
    status: TaskStatus
    agent: str = "scout_agent"
    result: Optional[ScoutTaskResult] = None
    error: Optional[str] = None
