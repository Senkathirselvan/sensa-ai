"""
LangGraph StateGraph for Job-Finding Agent (Scout).
Orchestrates:
  1. Query Planning & City Resolution
  2. Parallel Multi-Source Scraping (Naukri, LinkedIn, APIs)
  3. Deduplication & Normalization
  4. LLM Match Scoring & Ranking
  5. Final Output Formatting
"""
import asyncio
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END

from scout_agent.app.state import ScoutGraphState
from scout_agent.app.skills.query_planner import plan_search_cities, extract_skills_from_text
from scout_agent.app.skills.search_naukri import search_naukri
from scout_agent.app.skills.search_linkedin import search_linkedin
from scout_agent.app.skills.search_web_apis import search_tech_apis
from scout_agent.app.skills.deduplicate import deduplicate_jobs
from scout_agent.app.skills.scorer import score_and_rank_jobs


async def query_planner_node(state: ScoutGraphState) -> Dict[str, Any]:
    """Node 1: Resolves target cities and extracts skills from resume if provided."""
    location = state.get("location", "India")
    specified_cities = state.get("cities") or []

    if specified_cities:
        cities = specified_cities
    else:
        cities = plan_search_cities(location)

    resume_text = state.get("resume_text", "")
    extracted_skills = extract_skills_from_text(resume_text) if resume_text else []

    return {
        "cities": cities,
        "extracted_skills": extracted_skills
    }


async def parallel_fetch_node(state: ScoutGraphState) -> Dict[str, Any]:
    """Node 2: Concurrently queries Naukri, LinkedIn, and Tech APIs across target cities."""
    role = state.get("role", "Software Engineer")
    cities = state.get("cities", ["India"])
    limit = state.get("limit", 10)

    tasks = []

    # Naukri searches per city
    for city in cities[:3]:  # Top 3 cities max per query batch
        tasks.append(search_naukri(role=role, city=city, limit=limit))

    # LinkedIn search
    main_loc = cities[0] if cities else "India"
    tasks.append(search_linkedin(role=role, location=main_loc, limit=limit))

    # Direct Web Tech APIs
    tasks.append(search_tech_apis(role=role, location=main_loc, limit=limit))

    # Run in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)

    raw_jobs = []
    for batch in results:
        if isinstance(batch, list):
            raw_jobs.extend(batch)

    return {"raw_jobs": raw_jobs}


async def deduplicate_node(state: ScoutGraphState) -> Dict[str, Any]:
    """Node 3: Removes duplicates and normalizes URLs."""
    raw_jobs = state.get("raw_jobs", [])
    deduped = deduplicate_jobs(raw_jobs)
    return {"deduped_jobs": deduped}


async def score_node(state: ScoutGraphState) -> Dict[str, Any]:
    """Node 4: Evaluates candidate fit using LLM scoring."""
    jobs_to_score = state.get("deduped_jobs", [])
    skills = state.get("extracted_skills", [])
    role = state.get("role", "Software Engineer")

    # Score jobs
    scored = await score_and_rank_jobs(jobs=jobs_to_score, target_skills=skills, role=role)
    return {"final_jobs": scored}


async def format_node(state: ScoutGraphState) -> Dict[str, Any]:
    """Node 5: Trims to limit and sets total count."""
    final_jobs = state.get("final_jobs", [])
    limit = state.get("limit", 10)
    trimmed = final_jobs[:limit]

    return {
        "final_jobs": trimmed,
        "total_found": len(final_jobs)
    }


def build_scout_graph():
    """Builds and compiles the Scout LangGraph StateGraph."""
    builder = StateGraph(ScoutGraphState)

    # Add Nodes
    builder.add_node("query_planner", query_planner_node)
    builder.add_node("parallel_fetch", parallel_fetch_node)
    builder.add_node("deduplicate", deduplicate_node)
    builder.add_node("scorer", score_node)
    builder.add_node("formatter", format_node)

    # Add Edges (Linear sequential execution with parallel internal fetch)
    builder.add_edge(START, "query_planner")
    builder.add_edge("query_planner", "parallel_fetch")
    builder.add_edge("parallel_fetch", "deduplicate")
    builder.add_edge("deduplicate", "scorer")
    builder.add_edge("scorer", "formatter")
    builder.add_edge("formatter", END)

    return builder.compile()


# Pre-compiled graph ready for invocation
scout_graph = build_scout_graph()
