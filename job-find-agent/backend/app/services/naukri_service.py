import os
import sys
import json
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright

# Include shared package
SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "shared")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

try:
    from session_manager import load_naukri_cookies, get_naukri_session_path
except ImportError:
    def load_naukri_cookies():
        from backend.app.core.config import settings
        p = os.path.join(settings.DATA_DIR, "naukri_session.json")
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return None
    def get_naukri_session_path():
        from backend.app.core.config import settings
        return os.path.join(settings.DATA_DIR, "naukri_session.json")

def parse_job_age_days(posted_text: Optional[str]) -> int:
    """Parses relative age string like '2 days ago', 'Just Now', '3+ weeks ago', '30+ days ago' into integer days."""
    if not posted_text:
        return 999
    txt = posted_text.lower().strip()
    if any(x in txt for x in ["just now", "today", "few hours", "hour", "hours"]):
        return 0
    m = re.search(r"(\d+)\+?\s*day", txt)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\+?\s*week", txt)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\+?\s*month", txt)
    if m:
        return int(m.group(1)) * 30
    return 999

async def search_naukri_jobs(role: str, location: str = "india", limit: int = 6, days: Optional[int] = None) -> List[Dict]:
    """
    Scrapes live jobs from Naukri.com using Playwright Async API.
    Supports filtering by days (e.g. days=5 passes ?jobAge=5 and parses posted dates).
    """
    if not os.getenv("DISPLAY"):
        os.environ["DISPLAY"] = ":99"

    try:
        clean_role = re.sub(r"[^a-zA-Z0-9\s]", "", role).strip().lower()
        role_slug = "-".join(clean_role.split()) or "software-developer"

        clean_loc = re.sub(r"[^a-zA-Z0-9\s]", "", location).strip().lower()
        loc_slug = "-".join(clean_loc.split()) or "india"

        # If location is broadly India, Naukri's primary clean URL is {role_slug}-jobs
        if loc_slug in ["india", "all-india", "pan-india", "anywhere", "all"]:
            url = f"https://www.naukri.com/{role_slug}-jobs"
            alt_url = f"https://www.naukri.com/{role_slug}-jobs-in-india"
        else:
            url = f"https://www.naukri.com/{role_slug}-jobs-in-{loc_slug}"
            alt_url = f"https://www.naukri.com/{role_slug}-jobs"

        if days:
            url += f"?jobAge={days}"
            alt_url += f"?jobAge={days}"

        print(f"[Naukri Scraper] Fetching: {url} (alt={alt_url}, limit={limit}, days={days})", flush=True)
        jobs = []

        cookies = load_naukri_cookies()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            if cookies:
                try:
                    await context.add_cookies(cookies)
                except Exception as ce:
                    print(f"[Naukri Scraper] Cookie notice: {ce}", flush=True)

            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_selector(
                    "div.srp-jobtuple-wrapper, div.cust-job-tuple, div[class*='styles_job-tuple'], a[href*='/job-listings-']",
                    state="attached",
                    timeout=20000
                )
            except Exception as ge:
                print(f"[Naukri Scraper] Selector wait notice on primary URL: {ge}", flush=True)
                try:
                    await page.evaluate("window.scrollBy(0, 400);")
                    await page.wait_for_timeout(2500)
                except Exception:
                    pass

            cards = await page.locator("div.srp-jobtuple-wrapper, div.cust-job-tuple, div[class*='styles_job-tuple']").all()

            if len(cards) == 0 and alt_url:
                print(f"[Naukri Scraper] Trying alternate URL: {alt_url}", flush=True)
                try:
                    await page.goto(alt_url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_selector(
                        "div.srp-jobtuple-wrapper, div.cust-job-tuple, div[class*='styles_job-tuple'], a[href*='/job-listings-']",
                        state="attached",
                        timeout=15000
                    )
                    cards = await page.locator("div.srp-jobtuple-wrapper, div.cust-job-tuple, div[class*='styles_job-tuple']").all()
                except Exception as ae:
                    print(f"[Naukri Scraper] Alternate URL notice: {ae}", flush=True)

            print(f"[Naukri Scraper] Found {len(cards)} cards on page", flush=True)

            seen_urls = set()
            for card in cards:
                if len(jobs) >= limit:
                    break
                try:
                    title_el = card.locator("a.title, a[title], a[href*='/job-listings-']").first
                    if await title_el.count() == 0:
                        continue
                    title = (await title_el.inner_text()).strip()
                    link = await title_el.get_attribute("href")
                    if not link or link in seen_urls:
                        continue
                    seen_urls.add(link)

                    if not link.startswith("http"):
                        link = f"https://www.naukri.com{link}"

                    comp_el = card.locator("a.comp-name, .companyInfo a, a.subTitle, span.comp-name").first
                    company = (await comp_el.inner_text()).strip() if await comp_el.count() > 0 else "Hiring Company"

                    loc_el = card.locator(".locwdth, .loc-wrap, span[class*='loc']").first
                    loc = (await loc_el.inner_text()).strip() if await loc_el.count() > 0 else location.capitalize()

                    exp_el = card.locator(".expwdth, .exp-wrap, span[class*='exp']").first
                    exp = (await exp_el.inner_text()).strip() if await exp_el.count() > 0 else None

                    sal_el = card.locator(".salwdth, .sal-wrap, span[class*='sal']").first
                    sal = (await sal_el.inner_text()).strip() if await sal_el.count() > 0 else None

                    desc_el = card.locator(".job-desc, .ellipsis, span[class*='job-desc']").first
                    desc = (await desc_el.inner_text()).strip() if await desc_el.count() > 0 else ""

                    date_el = card.locator("span.job-post-day, span[class*='job-post-day']").first
                    posted_date = (await date_el.inner_text()).strip() if await date_el.count() > 0 else None

                    # If days filter is specified, verify that the card's posted age meets the criteria
                    if days is not None and posted_date:
                        age = parse_job_age_days(posted_date)
                        if age > days:
                            continue

                    candidate_job = {
                        "platform": "Naukri",
                        "title": title,
                        "company": company,
                        "location": loc,
                        "experience": exp,
                        "salary": sal,
                        "posted_date": posted_date,
                        "url": link,
                        "snippet": desc[:300],
                        "source": "live_naukri"
                    }
                    try:
                        from backend.app.services.search_service import is_job_relevant
                        if is_job_relevant(candidate_job, role):
                            jobs.append(candidate_job)
                    except Exception:
                        jobs.append(candidate_job)
                except Exception:
                    continue

            # Fallback extraction from direct links if needed
            if len(jobs) == 0:
                print("[Naukri Scraper] Attempting fallback extraction from direct links...", flush=True)
                links = await page.locator("a[href*='/job-listings-']").all()
                for l in links:
                    if len(jobs) >= limit:
                        break
                    try:
                        href = await l.get_attribute("href")
                        title = (await l.inner_text()).strip()
                        if href and href not in seen_urls and len(title) > 3:
                            seen_urls.add(href)
                            if not href.startswith("http"):
                                href = f"https://www.naukri.com{href}"

                            parent = l.locator("xpath=../../..")
                            company = "Hiring Company"
                            try:
                                comp_el = parent.locator("a.comp-name, .companyInfo a, a.subTitle, span.comp-name").first
                                if await comp_el.count() > 0:
                                    company = (await comp_el.inner_text()).strip()
                            except Exception:
                                pass

                            posted_date = "Recently"
                            try:
                                date_el = parent.locator("span.job-post-day, span[class*='job-post-day']").first
                                if await date_el.count() > 0:
                                    posted_date = (await date_el.inner_text()).strip()
                            except Exception:
                                pass

                            candidate_job = {
                                "platform": "Naukri",
                                "title": title,
                                "company": company,
                                "location": location.capitalize() if location.lower() != "india" else "Pan India",
                                "experience": None,
                                "salary": None,
                                "posted_date": posted_date,
                                "url": href,
                                "snippet": "",
                                "source": "live_naukri"
                            }
                            try:
                                from backend.app.services.search_service import is_job_relevant
                                if is_job_relevant(candidate_job, role):
                                    jobs.append(candidate_job)
                            except Exception:
                                jobs.append(candidate_job)
                    except Exception:
                        continue

            await browser.close()
        jobs.sort(key=lambda j: parse_job_age_days(j.get("posted_date")))
        return jobs[:limit]
    except Exception as e:
        print(f"[Naukri Scraper Error] {e}", flush=True)
        return []

async def search_naukri_multi_city(role: str, cities: List[str] = None, limit: int = 6, location: str = "india", days: Optional[int] = None) -> List[Dict]:
    """Searches across cities or countrywide."""
    if not cities or len(cities) == 0:
        return await search_naukri_jobs(role, location=location, limit=limit, days=days)
    
    if len(cities) == 1 and cities[0].lower() in ["india", "all india", "remote"]:
        return await search_naukri_jobs(role, location=cities[0], limit=limit, days=days)

    all_jobs = []
    per_city = max(2, limit // max(1, len(cities)))
    for city in cities:
        city_jobs = await search_naukri_jobs(role, location=city, limit=per_city, days=days)
        all_jobs.extend(city_jobs)
    all_jobs.sort(key=lambda j: parse_job_age_days(j.get("posted_date")))
    return all_jobs[:limit]
