"""
Week 1: JobSpy + Ollama City Planner
Searches LinkedIn and Indeed using python-jobspy.
Uses Ollama to resolve broad locations to specific Indian cities.
"""

import os
import json
import ollama
from typing import List, Dict

SAMPLE_JOBS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_jobs.json")
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen2.5")


def resolve_cities_with_ollama(location_preference: str) -> List[str]:
    if "remote" in location_preference.lower():
        return ["Remote"]
    prompt = f"""
The user wants jobs in: "{location_preference}".
Return ONLY a JSON list of 3 major Indian tech cities. No markdown. No explanation.
Valid choices: Bengaluru, Hyderabad, Pune, Chennai, Mumbai, Delhi NCR, Kolkata.
Output only the list: ["City1", "City2", "City3"]
"""
    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response["message"]["content"].strip()
        start = content.find("[")
        end = content.rfind("]") + 1
        if start != -1 and end > start:
            cities = json.loads(content[start:end])
            return cities if isinstance(cities, list) and cities else ["Bengaluru"]
    except Exception:
        pass
    return ["Bengaluru", "Hyderabad", "Pune"]


def fetch_jobs_with_jobspy(role: str, city: str, limit: int = 5) -> List[Dict]:
    try:
        from jobspy import scrape_jobs
        import pandas as pd
        df = scrape_jobs(
            site_name=["linkedin", "indeed"],
            search_term=role,
            location=city,
            results_wanted=limit,
            hours_old=72,
            country_indeed="india",
        )
        if df.empty:
            return []
        df = df[["site", "title", "company", "location", "job_url", "description"]].fillna("")
        return [
            {
                "platform": str(j.get("site", "")).capitalize(),
                "title": str(j.get("title", "")),
                "company": str(j.get("company", "")),
                "location": str(j.get("location", city)),
                "url": str(j.get("job_url", "")),
                "snippet": str(j.get("description", ""))[:400],
                "source": "live"
            }
            for j in df.to_dict(orient="records")
        ]
    except Exception as e:
        print(f"[JobSpy Error] {city}: {e}")
        return []


def load_fallback_jobs(role: str) -> List[Dict]:
    if os.path.exists(SAMPLE_JOBS_PATH):
        try:
            with open(SAMPLE_JOBS_PATH, "r") as f:
                all_jobs = json.load(f)
            keywords = [k.lower() for k in role.split() if len(k) > 2]
            matched = [j for j in all_jobs if any(kw in j.get("title","").lower() or kw in j.get("snippet","").lower() for kw in keywords)]
            result = matched if matched else all_jobs[:4]
            for item in result:
                item["source"] = "offline_fallback"
                item["note"] = "Offline sample - install python-jobspy for live results."
            return result
        except Exception:
            pass
    return [{"message": f"No jobs found for '{role}'."}]


def search_web_jobs(role: str, location: str = "India", limit: int = 6) -> List[Dict]:
    if not role or not role.strip():
        return [{"message": "Please provide a job role (e.g. 'Python Developer')."}]
    clean_role = role.strip()
    cities = resolve_cities_with_ollama(location)
    print(f"[City Planner] '{location}' -> {cities}")
    all_jobs = []
    for city in cities:
        city_jobs = fetch_jobs_with_jobspy(clean_role, city, limit=max(3, limit // len(cities) + 1))
        all_jobs.extend(city_jobs)
        if len(all_jobs) >= limit:
            break
    if all_jobs:
        return all_jobs[:limit]
    print("[Search] No live results - using local fallback.")
    return load_fallback_jobs(clean_role)
