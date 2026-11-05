"""
Automated Test Harness for Job-Finding Agent (Scout).
Run via:
  pytest scout_agent/app/harness/test_scout.py -v
  OR
  python3 -m scout_agent.app.harness.test_scout --role "Python Developer" --location "Chennai"
"""
import sys
import os
import asyncio
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from scout_agent.app.skills.query_planner import plan_search_cities, extract_skills_from_text
from scout_agent.app.skills.deduplicate import deduplicate_jobs
from scout_agent.app.skills.scorer import score_and_rank_jobs
from scout_agent.app.graph import scout_graph


def test_query_planner_city_lock():
    """Verify that specific cities are locked and not overridden."""
    cities_chennai = plan_search_cities("Chennai")
    assert cities_chennai == ["Chennai"]

    cities_bengaluru = plan_search_cities("Bengaluru")
    assert cities_bengaluru == ["Bengaluru"]

    cities_india = plan_search_cities("India")
    assert "Bengaluru" in cities_india
    assert "Chennai" in cities_india


def test_query_planner_resume_skills():
    """Verify skill extraction from sample resume snippet."""
    resume_snippet = "Experienced developer working with Python, FastAPI, Docker, and PostgreSQL databases."
    skills = extract_skills_from_text(resume_snippet)
    assert "Python" in skills
    assert "Fastapi" in skills or "FastAPI" in skills or "fastapi" in [s.lower() for s in skills]
    assert "Docker" in skills


def test_deduplicator():
    """Verify duplicate jobs are removed."""
    sample_jobs = [
        {"title": "Python Developer", "company": "Tech Corp", "url": "https://example.com/job1?utm_source=feed"},
        {"title": "Python Developer", "company": "Tech Corp", "url": "https://example.com/job1?ref=linkedin"},
        {"title": "Backend Engineer", "company": "Another Co", "url": "https://example.com/job2"}
    ]
    deduped = deduplicate_jobs(sample_jobs)
    assert len(deduped) == 2
    assert deduped[0]["url"] == "https://example.com/job1"


@pytest.mark.asyncio
async def test_scorer():
    """Verify job scoring outputs valid 0-100 score."""
    sample_jobs = [
        {"title": "Senior Python Developer", "company": "Acme Inc", "description_snippet": "Looking for FastAPI, Docker, Postgres expert."}
    ]
    scored = await score_and_rank_jobs(sample_jobs, ["Python", "FastAPI"], "Python Developer")
    assert len(scored) == 1
    assert 0 <= scored[0]["match_score"] <= 100
    assert "matched_skills" in scored[0]


@pytest.mark.asyncio
async def test_scout_graph_execution():
    """End-to-end execution of Scout LangGraph pipeline."""
    initial_state = {
        "role": "Python Developer",
        "location": "Chennai",
        "limit": 3
    }
    result = await scout_graph.ainvoke(initial_state)
    assert "final_jobs" in result
    assert isinstance(result["final_jobs"], list)
    print(f"\n✅ Scout Graph returned {len(result['final_jobs'])} jobs.")
    for j in result["final_jobs"]:
        print(f"   - [{j.get('match_score')}%] {j.get('title')} at {j.get('company')} ({j.get('location')})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="Python Developer")
    parser.add_argument("--location", default="Chennai")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    print(f"🚀 Running Live Scout Agent LangGraph Test for '{args.role}' in '{args.location}'...")
    state = {
        "role": args.role,
        "location": args.location,
        "limit": args.limit
    }
    res = asyncio.run(scout_graph.ainvoke(state))
    print(f"\n🎯 Total Jobs Found: {res.get('total_found')}")
    for idx, job in enumerate(res.get("final_jobs", []), 1):
        print(f"{idx}. {job.get('title')} - {job.get('company')} ({job.get('location')})")
        print(f"   Score: {job.get('match_score')}% | Source: {job.get('source')}")
        print(f"   URL: {job.get('url')}\n")
