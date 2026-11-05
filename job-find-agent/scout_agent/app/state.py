"""
LangGraph State definition for Scout Agent.
"""
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class ScoutGraphState(TypedDict, total=False):
    # Inputs
    role: str
    location: str
    cities: List[str]
    limit: int
    resume_text: Optional[str]

    # Intermediate State
    extracted_skills: List[str]
    raw_jobs: List[Dict[str, Any]]
    deduped_jobs: List[Dict[str, Any]]

    # Output State
    final_jobs: List[Dict[str, Any]]
    total_found: int
    error: Optional[str]
