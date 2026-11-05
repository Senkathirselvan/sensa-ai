"""
Skill: Naukri Scraper & Session Authenticator
Fetches live Naukri job postings using a dual-engine architecture:
  1. Headless Playwright browser with authenticated Session Cookies (naukri_session.json)
     - Bypasses Akamai/Cloudflare Bot Challenge
     - Uses realistic user-agent & stealth flags
     - Extracts rich job details (Title, Company, Exp, Salary, Location, Snippet, URL)
  2. Search Engine Indexer fallback (if session cookies are absent or expired)
"""
import os
import re
import urllib.parse
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup

from shared.session_manager import load_naukri_cookies, get_naukri_session_path


def _format_slug(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    return re.sub(r'[\s_]+', '-', cleaned).strip('-').lower()


async def search_naukri_via_indexer(role: str, city: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fallback Engine: Fetches real, live Naukri jobs via search engine aggregation.
    Used when session cookies are absent or expired.
    """
    jobs = []
    query = f"site:naukri.com/job-listings \"{role}\" \"{city}\""
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
            res = await client.get(search_url)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                results = soup.select(".result")

                for r in results:
                    if len(jobs) >= limit:
                        break

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

                    if "naukri.com" not in actual_url:
                        continue

                    clean_title = re.sub(r"\s*-\s*Naukri\.com.*$", "", raw_title, flags=re.I)
                    clean_title = re.sub(r"\s*\|\s*Naukri.*$", "", clean_title, flags=re.I)

                    company_match = re.search(r"at\s+([A-Za-z0-9\s]+?)(?:in|\.|\,|$)", raw_snippet, re.I)
                    company = company_match.group(1).strip() if company_match else "Naukri Verified Company"

                    job_id = f"naukri_{abs(hash(actual_url)) % 1000000}"

                    jobs.append({
                        "id": job_id,
                        "title": clean_title,
                        "company": company,
                        "location": city.title(),
                        "url": actual_url,
                        "source": "naukri",
                        "salary": None,
                        "experience": None,
                        "description_snippet": raw_snippet[:300]
                    })
    except Exception as e:
        print(f"[Naukri Indexer Warning] {e}")

    return jobs


async def search_naukri(role: str, city: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Main Naukri search skill.
    Loads session cookies from naukri_session.json to bypass Cloudflare/Akamai bot challenge.
    """
    role_slug = _format_slug(role)
    city_slug = _format_slug(city)
    target_url = f"https://www.naukri.com/{role_slug}-jobs-in-{city_slug}"

    cookies = load_naukri_cookies()
    cookie_path = get_naukri_session_path()

    jobs = []

    # Attempt 1: Playwright with Session Cookies
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
                locale="en-IN"
            )

            # Injected Session Cookies
            if cookies:
                print(f"[Naukri] 🍪 Injecting {len(cookies)} session cookies from {cookie_path}...")
                try:
                    await context.add_cookies(cookies)
                except Exception as ce:
                    print(f"[Naukri] Cookie injection notice: {ce}")
            else:
                print(f"[Naukri] ⚠️ No session cookies found at {cookie_path}. Attempting stealth visit...")

            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            
            # Navigate to Naukri
            try:
                await page.goto(target_url, timeout=18000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)
            except Exception as ge:
                print(f"[Naukri Navigation Warning] {ge}")

            title = await page.title()
            
            # Check for bot challenge block
            if "access denied" in title.lower() or "blocked" in title.lower():
                print(f"[Naukri] 🚫 Blocked by Bot Challenge ('{title}'). Session cookie needed or expired.")
                await browser.close()
                return await search_naukri_via_indexer(role, city, limit)

            # Extract job cards
            cards = await page.locator(
                "article.jobTuple, div.cust-job-tuple, .srp-jobtuple-wrapper, div[class*='styles_job-tuple-container']"
            ).all()

            print(f"[Naukri] Found {len(cards)} job card elements on page")

            for card in cards[:limit]:
                try:
                    title_el = card.locator("a.title, a[title]").first
                    company_el = card.locator("a.comp-name, .companyInfo a, a.subTitle, span.comp-name").first
                    exp_el = card.locator(".expwdth, .exp-wrap, span[class*='expwdth']").first
                    sal_el = card.locator(".salwdth, .sal-wrap, span[class*='sal']").first
                    loc_el = card.locator(".locwdth, .loc-wrap, span[class*='loc']").first
                    desc_el = card.locator(".job-desc, .ellipsis, span[class*='job-desc']").first

                    t = await title_el.inner_text() if await title_el.count() > 0 else "Tech Role"
                    comp = await company_el.inner_text() if await company_el.count() > 0 else "Hiring Company"
                    link = await title_el.get_attribute("href") if await title_el.count() > 0 else target_url
                    exp = await exp_el.inner_text() if await exp_el.count() > 0 else None
                    sal = await sal_el.inner_text() if await sal_el.count() > 0 else None
                    loc = await loc_el.inner_text() if await loc_el.count() > 0 else city.title()
                    desc = await desc_el.inner_text() if await desc_el.count() > 0 else f"Job opportunity for {t} at {comp}"

                    if link and not link.startswith("http"):
                        link = f"https://www.naukri.com{link}"

                    jobs.append({
                        "id": f"naukri_{abs(hash(link)) % 1000000}",
                        "title": t.strip(),
                        "company": comp.strip(),
                        "location": loc.strip(),
                        "url": link,
                        "source": "naukri",
                        "salary": sal.strip() if sal else None,
                        "experience": exp.strip() if exp else None,
                        "description_snippet": desc.strip()[:300]
                    })
                except Exception as card_e:
                    continue

            await browser.close()
    except Exception as e:
        print(f"[Naukri Playwright Error] {e}")

    # If Playwright yielded 0 results or was blocked, use Indexer Fallback
    if not jobs:
        print("[Naukri] Falling back to search indexer engine...")
        jobs = await search_naukri_via_indexer(role, city, limit)

    return jobs
