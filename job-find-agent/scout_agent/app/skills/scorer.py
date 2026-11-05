"""
Skill: LLM Match Scorer
Scores and ranks job postings against target skills or resume text using free LLMs.
"""
import json
import re
import asyncio
from typing import List, Dict, Any, Optional
import sys
import os

# Add parent path to import shared modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from shared.llm_factory import get_agent_llm


def _heuristic_score(job: Dict[str, Any], target_skills: List[str]) -> Dict[str, Any]:
    """Fallback keyword matching heuristic if LLM is unavailable."""
    title_text = (job.get("title", "") + " " + job.get("description_snippet", "")).lower()
    matched = []
    missing = []

    for s in target_skills:
        if s.lower() in title_text:
            matched.append(s)
        else:
            missing.append(s)

    if not target_skills:
        score = 80
        summary = "Standard match based on role title."
    else:
        score = int((len(matched) / max(len(target_skills), 1)) * 50) + 45
        score = min(score, 98)
        summary = f"Matches {len(matched)} of {len(target_skills)} target skills."

    return {
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "match_summary": summary
    }


async def score_single_job(job: Dict[str, Any], target_skills: List[str], role: str, llm=None) -> Dict[str, Any]:
    """Scores a single job posting using LLM with heuristic fallback."""
    if not llm:
        return _heuristic_score(job, target_skills)

    prompt = f"""You are a technical recruiter. Evaluate this job posting against the target candidate profile.

Target Role: {role}
Target Skills: {', '.join(target_skills) if target_skills else 'Standard tech skills for this role'}

Job Posting:
Title: {job.get('title')}
Company: {job.get('company')}
Description Snippet: {job.get('description_snippet')}

Return ONLY valid JSON matching this exact structure:
{{
  "match_score": <integer 0 to 100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3"],
  "match_summary": "<concise 1-sentence assessment>"
}}"""

    try:
        response = await asyncio.wait_for(llm.ainvoke(prompt), timeout=6.0)
        content = response.content.strip()

        # Extract JSON from code fences if present
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return {
                "match_score": int(data.get("match_score", 75)),
                "matched_skills": data.get("matched_skills", []),
                "missing_skills": data.get("missing_skills", []),
                "match_summary": data.get("match_summary", "Fit based on job title.")
            }
    except Exception:
        pass

    return _heuristic_score(job, target_skills)


async def score_and_rank_jobs(
    jobs: List[Dict[str, Any]],
    target_skills: List[str],
    role: str
) -> List[Dict[str, Any]]:
    """Scores all candidate jobs in parallel and returns them sorted by match score."""
    if not jobs:
        return []

    try:
        llm = get_agent_llm()
    except Exception:
        llm = None

    tasks = [score_single_job(job, target_skills, role, llm) for job in jobs]
    scores = await asyncio.gather(*tasks)

    for job, score_info in zip(jobs, scores):
        job.update(score_info)

    # Sort descending by match_score
    jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)
    return jobs
