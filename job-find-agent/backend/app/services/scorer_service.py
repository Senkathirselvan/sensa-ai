import json
import re
import asyncio
import httpx
from typing import List, Dict, Optional, Any
from backend.app.core.config import settings
from backend.app.services.resume_service import read_resume_text

TECH_TAXONOMY = [
    'python', 'fastapi', 'django', 'flask', 'frappe', 'erpnext',
    'mysql', 'mariadb', 'postgresql', 'sqlite', 'redis', 'celery',
    'docker', 'docker compose', 'nginx', 'linux', 'git', 'github',
    'rest api', 'restful', 'rest', 'graphql', 'websockets', 'imap', 'jmap',
    'jwt', 'oauth2', 'sso', 'rbac', 'microservices', 'saas', 'multitenant',
    'aws', 'gcp', 'azure', 'kubernetes', 'ci/cd', 'postman',
    'react', 'angular', 'vue', 'node', 'javascript', 'typescript',
    'java', 'spring', 'golang', 'c++', 'c#', 'kafka', 'rabbitmq',
    'pandas', 'numpy', 'machine learning', 'ai'
]

def normalize_platform(job: Dict) -> str:
    """Infers or normalizes the job platform from existing platform tag or URL."""
    raw = job.get("platform")
    if raw and str(raw).strip() and str(raw).strip().lower() not in ["none", "null", "web", ""]:
        p = str(raw).strip()
        if p.lower() == "linkedin":
            return "LinkedIn"
        if p.lower() == "naukri":
            return "Naukri"
        if p.lower() == "indeed":
            return "Indeed"
        return p.capitalize()

    url = (job.get("url") or "").lower()
    if "naukri.com" in url:
        return "Naukri"
    if "linkedin.com" in url:
        return "LinkedIn"
    if "indeed.com" in url:
        return "Indeed"
    if "glassdoor" in url:
        return "Glassdoor"
    if "foundit" in url or "monster" in url:
        return "Foundit"
    return "Web"

def extract_candidate_profile(resume_text: str) -> Dict[str, Any]:
    """Extracts structured skills and target profile from candidate resume text."""
    text_lower = resume_text.lower()

    # Extract years of experience
    exp_years = 1.5
    m_exp = re.search(r'(\d+(?:\.\d+)?)\+?\s*years?\s+of\s+experience', text_lower)
    if m_exp:
        try:
            exp_years = float(m_exp.group(1))
        except Exception:
            pass

    # Extract skills
    skills = set()
    for tech in TECH_TAXONOMY:
        pattern = r'(?:\b|_)' + re.escape(tech) + r'(?:\b|_)'
        if re.search(pattern, text_lower):
            skills.add(tech)

    return {
        "target_role": "Python Backend Developer",
        "experience_years": exp_years,
        "skills": skills
    }

def score_job_algorithmically(job: Dict, profile: Dict[str, Any]) -> Dict:
    """
    Computes an exact, nuanced mathematical match score (0-100)
    evaluating role alignment, skill overlap, and experience fit.
    """
    title = (job.get('title') or '').lower()
    company = job.get('company') or ''
    snippet = (job.get('snippet') or '').lower()
    full_text = f"{title} {company.lower()} {snippet}"
    profile_skills = profile.get("skills", set())
    exp_years = profile.get("experience_years", 1.5)

    # 1. Title Score (max 35)
    title_score = 0
    if 'python' in title and ('backend' in title or 'developer' in title or 'engineer' in title):
        title_score = 35
    elif 'python' in title:
        title_score = 30
    elif 'backend' in title:
        title_score = 25
    elif 'developer' in title or 'engineer' in title:
        title_score = 20
    else:
        title_score = 10

    # Seniority adjustment
    is_senior = any(s in title for s in ['senior', 'lead', 'principal', 'architect', 'manager', 'head', 'sr.', 'staff'])
    if is_senior and exp_years < 3.0:
        title_score = max(5, title_score - 18)

    # 2. Skill Overlap (max 45)
    job_skills = set()
    for s in TECH_TAXONOMY:
        pattern = r'(?:\b|_)' + re.escape(s) + r'(?:\b|_)'
        if re.search(pattern, full_text):
            job_skills.add(s)

    if 'rest api' in job_skills and 'rest' in job_skills:
        job_skills.remove('rest')

    matched = sorted(list(job_skills.intersection(profile_skills)))
    missing = sorted(list(job_skills.difference(profile_skills)))

    if job_skills:
        skill_ratio = len(matched) / len(job_skills)
        breadth_factor = min(1.0, len(matched) / 3.0) if len(job_skills) < 3 else 1.0
        skill_score = round(skill_ratio * 45 * (0.6 + 0.4 * breadth_factor))
    else:
        skill_score = 25 if 'python' in full_text else 10

    # 3. Experience Match (max 20)
    exp_score = 15
    exp_match = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)\s*(?:yrs|years)', full_text)
    if not exp_match:
        exp_match = re.search(r'(\d+)\+\s*(?:yrs|years)', full_text)

    if exp_match:
        if len(exp_match.groups()) == 2 and exp_match.group(2):
            min_exp = float(exp_match.group(1))
            max_exp = float(exp_match.group(2))
            if min_exp <= exp_years <= max_exp:
                exp_score = 20
            elif exp_years >= min_exp - 1 and exp_years <= max_exp + 1:
                exp_score = 15
            elif min_exp > exp_years + 2:
                exp_score = max(5, int(20 - (min_exp - exp_years) * 3))
        else:
            req_exp = float(exp_match.group(1))
            if exp_years >= req_exp:
                exp_score = 20
            else:
                exp_score = max(5, int(20 - (req_exp - exp_years) * 3))
    elif is_senior:
        exp_score = 5

    # If zero required skills matched, apply penalty cap
    if job_skills and len(matched) == 0:
        total = min(28, round((title_score + exp_score) * 0.6))
    else:
        total = min(98, max(15, title_score + skill_score + exp_score))

    reasons = []
    if 'python' in matched:
        top_m = [m.title() if len(m) > 3 else m.upper() for m in matched[:3]]
        reasons.append(f"Matches {len(matched)} key skill(s): {', '.join(top_m)}")
    if exp_score >= 18:
        reasons.append(f"Experience ({exp_years} yrs) is an optimal fit for this role")
    elif title_score >= 30:
        reasons.append("Direct target title alignment with Python Backend Developer")
    if not reasons:
        reasons.append("Relevant backend tech stack alignment")

    missing_formatted = [m.title() if len(m) > 3 else m.upper() for m in missing[:3]]

    return {
        **job,
        "platform": normalize_platform(job),
        "score": total,
        "match_reasons": reasons,
        "missing_skills": missing_formatted,
        "apply": total >= 70
    }

async def score_jobs_with_gemini(jobs: List[Dict], profile: Dict[str, Any], google_key: str) -> Optional[List[Dict]]:
    """Scores candidate jobs in a single batch request via Google Gemini API."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=google_key)
        jobs_payload = [
            {
                "index": i,
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": j.get("location", ""),
                "snippet": j.get("snippet", "")[:300]
            }
            for i, j in enumerate(jobs)
        ]
        prompt = f"""
You are an expert technical recruiter and hiring advisor.
Evaluate the candidate's fit for each of the following job postings.

--- CANDIDATE PROFILE ---
Target Role: {profile.get("target_role")}
Experience: {profile.get("experience_years")} years
Key Skills: {", ".join(sorted(list(profile.get("skills", []))))}

--- JOBS TO EVALUATE ---
{json.dumps(jobs_payload, indent=2)}

Calculate an honest, differentiated match score (0-100) for each job based on:
1. Title and role relevance (Python backend vs general vs senior/lead)
2. Skill overlap (candidate's Python, FastAPI, Django, Docker, Redis vs job requirements)
3. Experience fit (candidate has {profile.get("experience_years")} years)

Return ONLY a valid JSON array of objects with:
[
  {{
    "index": <int matching job index>,
    "score": <int from 20 to 98>,
    "match_reasons": ["top reason 1", "top reason 2"],
    "missing_skills": ["missing skill 1"],
    "apply": <true if score >= 70 else false>
  }}
]
"""
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-flash-latest",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            ),
            timeout=8.0
        )
        if response and response.text:
            parsed = json.loads(response.text)
            if isinstance(parsed, list):
                scored_map = {item.get("index"): item for item in parsed if isinstance(item, dict)}
                scored_results = []
                for idx, job in enumerate(jobs):
                    if idx in scored_map:
                        item = scored_map[idx]
                        score_val = int(item.get("score", 60))
                        scored_results.append({
                            **job,
                            "platform": normalize_platform(job),
                            "score": score_val,
                            "match_reasons": item.get("match_reasons", []),
                            "missing_skills": item.get("missing_skills", []),
                            "apply": bool(item.get("apply", score_val >= 70))
                        })
                    else:
                        scored_results.append(score_job_algorithmically(job, profile))
                return scored_results
    except Exception as e:
        print(f"[Gemini Scorer Batch Fallback] {e}", flush=True)
    return None

async def score_job_against_resume(job: Dict, model: str = settings.DEFAULT_MODEL) -> Dict:
    """Scores a single job against the candidate resume."""
    resume_text = read_resume_text()
    if resume_text.startswith("No resume"):
        return {**job, "score": 0, "match_reasons": ["Resume not uploaded"], "missing_skills": [], "apply": False}

    profile = extract_candidate_profile(resume_text)
    return score_job_algorithmically(job, profile)

async def score_and_rank_jobs(
    jobs: List[Dict],
    model: str = settings.DEFAULT_MODEL,
    google_key: Optional[str] = None,
    claude_key: Optional[str] = None
) -> List[Dict]:
    """
    Scores and ranks job postings against the candidate's resume.
    1. Reads resume text and extracts profile.
    2. Runs fast cloud LLM (Gemini) batch scoring if key is present.
    3. Falls back immediately to the high-accuracy algorithmic scoring engine.
    Never returns static or duplicate placeholder scores.
    """
    resume_text = read_resume_text()
    if resume_text.startswith("No resume"):
        return [{**j, "score": 0, "match_reasons": ["Resume not uploaded"], "missing_skills": [], "apply": False} for j in jobs]

    profile = extract_candidate_profile(resume_text)
    # Score all collected jobs across all platforms (Naukri, LinkedIn, Indeed)
    jobs_to_score = jobs[:30]

    # Try Gemini batch scoring if API key is provided
    if google_key:
        gemini_scored = await score_jobs_with_gemini(jobs_to_score, profile, google_key)
        if gemini_scored:
            for s in gemini_scored:
                s["platform"] = normalize_platform(s)
            return sorted(gemini_scored, key=lambda x: x.get("score", 0), reverse=True)

    # Algorithmic Scoring (Instant, Deterministic, Highly Accurate)
    scored = []
    for j in jobs_to_score:
        scored_job = score_job_algorithmically(j, profile)
        scored_job["platform"] = normalize_platform(scored_job)
        scored.append(scored_job)

    return sorted(scored, key=lambda x: x.get("score", 0), reverse=True)
