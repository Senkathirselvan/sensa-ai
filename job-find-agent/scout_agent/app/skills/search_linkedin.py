"""
Skill: LinkedIn Public Job Search
Aggregates public LinkedIn job listings via public guest queries and search indexers.
"""
import re
import urllib.parse
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup


async def search_linkedin(role: str, location: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Finds real LinkedIn job postings using public guest API / DuckDuckGo search aggregator.
    """
    jobs = []

    # Method 1: Query DuckDuckGo HTML for site:linkedin.com/jobs/view
    query = f'site:linkedin.com/jobs/view "{role}" "{location}"'
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded}"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
            res = await client.get(search_url)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                results = soup.select(".result")

                for r in results:
                    if len(jobs) >= limit:
                        break

                    a_tag = r.select_one(".result__snippet, .result__url, a.result__url")
                    title_tag = r.select_one(".result__title, a.result__a")
                    snippet_tag = r.select_one(".result__snippet")

                    if not title_tag:
                        continue

                    raw_title = title_tag.get_text(strip=True)
                    raw_snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                    raw_href = title_tag.get("href", "")

                    # Extract actual target url from DuckDuckGo redirect uddg= parameter
                    match = re.search(r"uddg=([^&]+)", raw_href)
                    actual_url = urllib.parse.unquote(match.group(1)) if match else raw_href

                    if "linkedin.com/jobs" not in actual_url:
                        continue

                    # Parse Company and Title from "Role - Company - Location | LinkedIn"
                    clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", raw_title)
                    parts = clean_title.split(" - ")
                    job_title = parts[0].strip() if parts else raw_title
                    company = parts[1].strip() if len(parts) > 1 else "Tech Employer"

                    job_id = f"linkedin_{abs(hash(actual_url)) % 1000000}"

                    jobs.append({
                        "id": job_id,
                        "title": job_title,
                        "company": company,
                        "location": location,
                        "url": actual_url,
                        "source": "linkedin",
                        "salary": None,
                        "experience": None,
                        "description_snippet": raw_snippet
                    })
    except Exception:
        pass

    return jobs
