"""
Skill: Query Planner
Converts raw user prompt and/or resume text into targeted job search queries and city plans.
"""
from typing import List, Dict, Any, Optional
import re

KNOWN_CITIES = {
    "chennai": "Chennai",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "mumbai": "Mumbai",
    "gurgaon": "Gurgaon",
    "gurugram": "Gurgaon",
    "noida": "Noida",
    "delhi": "Delhi",
    "kolkata": "Kolkata",
    "kochi": "Kochi",
    "trivandrum": "Trivandrum",
    "coimbatore": "Coimbatore"
}

DEFAULT_TECH_HUBS = ["Bengaluru", "Hyderabad", "Chennai", "Pune"]


def plan_search_cities(location: str) -> List[str]:
    """
    Determines search cities deterministically.
    If a specific city is requested, locks strictly to that city.
    If 'India' or country-level, distributes across top tech hubs.
    """
    if not location:
        return DEFAULT_TECH_HUBS

    loc_lower = location.lower().strip()

    # Check for exact or substring match in known cities
    matched_cities = []
    for key, city_name in KNOWN_CITIES.items():
        if re.search(r'\b' + re.escape(key) + r'\b', loc_lower):
            matched_cities.append(city_name)

    if matched_cities:
        # Return unique matched cities in canonical capitalization
        return list(dict.fromkeys(matched_cities))

    if "remote" in loc_lower:
        return ["Remote"]

    if "india" in loc_lower or loc_lower in ["in", "all india"]:
        return DEFAULT_TECH_HUBS

    # Default fallback: return location as-is
    return [location.strip().title()]


def extract_skills_from_text(text: str) -> List[str]:
    """Quick regex extraction of common tech keywords from resume or JD snippet."""
    common_skills = [
        "python", "fastapi", "django", "flask", "react", "node.js", "nodejs",
        "typescript", "javascript", "docker", "kubernetes", "postgresql", "postgres",
        "mysql", "mongodb", "redis", "aws", "gcp", "azure", "ci/cd", "git",
        "rest api", "graphql", "langchain", "langgraph", "llm", "ai agent"
    ]
    text_lower = text.lower()
    found = []
    for skill in common_skills:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found.append(skill.title() if len(skill) > 3 else skill.upper())
    return list(dict.fromkeys(found))
