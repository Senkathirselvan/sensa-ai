"""
Skill: Direct Web Tech APIs
Queries public tech job APIs (Arbeitnow & RemoteOK) for verified live jobs.
"""
from typing import List, Dict, Any
import httpx


async def search_tech_apis(role: str, location: str = "India", limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches live developer jobs from free public APIs with zero API key required."""
    jobs = []

    # Source 1: Arbeitnow API (Free, no key needed)
    try:
        url = "https://www.arbeitnow.com/api/job-board-api"
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json().get("data", [])
                role_keywords = role.lower().split()
                for item in data:
                    if len(jobs) >= limit:
                        break
                    title = item.get("title", "")
                    title_lower = title.lower()
                    # Check keyword relevance
                    if any(kw in title_lower for kw in role_keywords if len(kw) > 2):
                        jobs.append({
                            "id": f"arbeit_{item.get('slug', str(hash(title))[:8])}",
                            "title": title,
                            "company": item.get("company_name", "Global Tech Co"),
                            "location": item.get("location", location),
                            "url": item.get("url", "https://www.arbeitnow.com"),
                            "source": "arbeitnow",
                            "salary": None,
                            "experience": None,
                            "description_snippet": item.get("description", "")[:250]
                        })
    except Exception:
        pass

    # Source 2: RemoteOK API (if remote or not enough jobs)
    if len(jobs) < limit:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)"}
            async with httpx.AsyncClient(headers=headers, timeout=8.0) as client:
                res = await client.get("https://remoteok.com/api", headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    role_keywords = role.lower().split()
                    for item in data[1:]:  # Skip metadata object
                        if len(jobs) >= limit:
                            break
                        pos = item.get("position", "")
                        tags = " ".join(item.get("tags", [])).lower()
                        if any(kw in pos.lower() or kw in tags for kw in role_keywords if len(kw) > 2):
                            jobs.append({
                                "id": f"remoteok_{item.get('id', str(hash(pos))[:8])}",
                                "title": pos,
                                "company": item.get("company", "Remote Tech"),
                                "location": "Remote",
                                "url": item.get("url", f"https://remoteok.com/remote-jobs/{item.get('id', '')}"),
                                "source": "remoteok",
                                "salary": item.get("salary_max", None),
                                "experience": None,
                                "description_snippet": item.get("description", "")[:250]
                            })
        except Exception:
            pass

    return jobs
