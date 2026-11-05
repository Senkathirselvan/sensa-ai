import os
import json
import httpx
from datetime import date, datetime
from typing import List, Dict
import pandas as pd
from backend.app.core.config import settings

SAMPLE_JOBS_PATH = os.path.join(settings.DATA_DIR, "sample_jobs.json")

KNOWN_CITIES = {
    "chennai": "Chennai",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "mumbai": "Mumbai",
    "delhi": "Delhi NCR",
    "noida": "Noida",
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "kolkata": "Kolkata",
    "coimbatore": "Coimbatore",
    "kochi": "Kochi",
    "ahmedabad": "Ahmedabad",
}

def format_relative_date(dt) -> str:
    """Formats a datetime/date object or string into human-friendly relative string (e.g. '3 days ago')."""
    if dt is None or (isinstance(dt, float) and pd.isna(dt)) or dt == "":
        return ""
    try:
        if isinstance(dt, str):
            dt_clean = dt.strip().split("T")[0]
            dt = datetime.strptime(dt_clean, "%Y-%m-%d").date()
        elif isinstance(dt, datetime):
            dt = dt.date()
        elif not isinstance(dt, date):
            return str(dt)

        diff = (date.today() - dt).days
        if diff <= 0:
            return "Today"
        elif diff == 1:
            return "1 day ago"
        elif diff < 7:
            return f"{diff} days ago"
        elif diff < 14:
            return "1 week ago"
        elif diff < 30:
            weeks = diff // 7
            return f"{weeks} weeks ago"
        elif diff < 60:
            return "1 month ago"
        else:
            months = diff // 30
            return f"{months} months ago"
    except Exception:
        return str(dt) if dt else ""

def is_job_relevant(job: Dict, target_role: str) -> bool:
    """
    Validates that a scraped job posting actually matches the requested role.
    Filters out junk, unrelated roles (Appium, CCTV, Telecaller, Internships),
    and enforces core skill presence.
    """
    title = (job.get("title") or "").lower()
    snippet = (job.get("snippet") or "").lower()
    role_lower = target_role.lower()

    # 1. Unwanted junk terms and negative patterns
    unwanted = [
        "intern", "internship", "appium", "cctv", "qa manual", "telecaller",
        "bpo", "graphic", "civil", "sales", "marketing", "content writer",
        "hardware", "receptionist", "data entry"
    ]
    if any(u in title and u not in role_lower for u in unwanted):
        return False

    # 2. Extract technical anchor terms from target role
    tech_anchors = [
        "python", "django", "fastapi", "flask", "java", "react", "golang", "go",
        "angular", "flutter", "vue", "node", "nodejs", "c++", "rust", "php",
        "ruby", "dotnet", ".net", "backend", "full stack", "fullstack", "devops",
        "cloud", "aws", "data engineer"
    ]
    matched_anchors = [a for a in tech_anchors if a in role_lower.split() or a in role_lower]

    if matched_anchors:
        # At least one core anchor MUST be in the job title!
        has_anchor_in_title = any(a in title for a in matched_anchors)
        if not has_anchor_in_title:
            return False

    # 3. If a specific programming language/technology is explicitly in the user query:
    languages = [
        "python", "java", "golang", "go", "react", "angular", "flutter",
        "vue", "rust", "c++", "c#", "php", "ruby", "django", "fastapi", "flask"
    ]
    langs_in_role = [lang for lang in languages if lang in role_lower.split() or lang in role_lower]
    if langs_in_role:
        # At least one requested language must appear in title OR snippet
        if not any(lang in title or lang in snippet for lang in langs_in_role):
            return False

    # 4. If user asked for "backend", filter out purely frontend roles unless full stack
    if "backend" in role_lower and "frontend" in title and "backend" not in title and "full" not in title:
        return False

    return True

async def resolve_cities(location: str, model: str = "qwen2.5") -> List[str]:
    if not location or not location.strip():
        return ["Bengaluru", "Chennai", "Hyderabad"]

    loc_lower = location.lower()

    if "remote" in loc_lower:
        return ["Remote"]

    # Direct city matching
    matched = [city_name for key, city_name in KNOWN_CITIES.items() if key in loc_lower]
    if matched:
        return list(dict.fromkeys(matched))

    # If the user specified a specific city/place not in KNOWN_CITIES, preserve it directly!
    if loc_lower not in ["india", "pan india", "anywhere", "all india"]:
        return [location.strip().title()]

    # If broad location like "India", search top hubs
    return ["Bengaluru", "Chennai", "Hyderabad", "Pune"]

def fetch_jobs_with_jobspy(role: str, city: str, limit: int = 4, days: int = None) -> List[Dict]:
    try:
        from jobspy import scrape_jobs
        hours = max(24, days * 24) if days else 72
        # Prioritize LinkedIn Easy Apply jobs so the autonomous apply agent can submit in-app without external redirection
        df = None
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=role,
                location=city,
                results_wanted=max(8, limit * 2),
                hours_old=hours,
                easy_apply=True,
                country_indeed="india",
            )
        except Exception as e_ea:
            print(f"[JobSpy EasyApply] {city}: {e_ea}")

        if df is None or df.empty:
            df = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=role,
                location=city,
                results_wanted=max(8, limit * 2),
                hours_old=hours,
                country_indeed="india",
            )
        if df is None or df.empty:
            return []

        available_cols = [c for c in ["site", "title", "company", "location", "job_url", "description", "date_posted"] if c in df.columns]
        df_clean = df[available_cols].copy()

        raw_jobs = []
        for j in df_clean.to_dict(orient="records"):
            raw_date = j.get("date_posted")
            posted_str = format_relative_date(raw_date)
            raw_jobs.append({
                "platform": str(j.get("site", "Web")).capitalize(),
                "title": str(j.get("title", "") or ""),
                "company": str(j.get("company", "") or ""),
                "location": str(j.get("location", city) or city),
                "url": str(j.get("job_url", "") or ""),
                "snippet": str(j.get("description", "") or "")[:400],
                "posted_date": posted_str,
                "source": "live"
            })

        # Apply strict relevance filtering and sort by recency (newest first)
        from backend.app.services.naukri_service import parse_job_age_days
        relevant_jobs = [j for j in raw_jobs if is_job_relevant(j, role)]
        relevant_jobs.sort(key=lambda j: parse_job_age_days(j.get("posted_date")))
        return relevant_jobs[:limit]
    except Exception as e:
        print(f"[JobSpy Search Error] {city}: {e}")
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
                item["platform"] = item.get("platform", "LinkedIn")
                item["posted_date"] = item.get("posted_date", "Recently")
                item["note"] = "Live search unavailable - displaying offline verified sample."
            return result
        except Exception:
            pass
    return [
        {
            "platform": "LinkedIn",
            "title": f"Senior {role}",
            "company": "Tech Corp India",
            "location": "Bengaluru / Remote",
            "url": "https://linkedin.com",
            "snippet": f"Looking for experienced {role} with strong hands-on skills in APIs, databases, and microservices.",
            "posted_date": "Recently",
            "source": "demo"
        }
    ]

async def search_web_jobs(role: str, location: str = "India", limit: int = 6, days: int = None) -> List[Dict]:
    if not role or not role.strip():
        return [{"message": "Please specify a job role."}]
    clean_role = role.strip()
    cities = await resolve_cities(location)
    all_jobs = []
    
    for city in cities:
        city_jobs = fetch_jobs_with_jobspy(clean_role, city, limit=max(3, limit // len(cities) + 1), days=days)
        all_jobs.extend(city_jobs)
        if len(all_jobs) >= limit:
            break
            
    if all_jobs:
        from backend.app.services.naukri_service import parse_job_age_days
        all_jobs.sort(key=lambda j: parse_job_age_days(j.get("posted_date")))
        return all_jobs[:limit]
    return load_fallback_jobs(clean_role)
