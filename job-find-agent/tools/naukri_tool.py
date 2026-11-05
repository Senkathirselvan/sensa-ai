"""
Tools: Playwright Naukri Scraper with Session Cookie Support
Scrapes live Naukri job listings using Playwright and authenticated session cookies.
"""
import os
import sys
import json
from typing import List, Dict

# Include shared package
SHARED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared")
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

try:
    from session_manager import load_naukri_cookies, get_naukri_session_path
except ImportError:
    def load_naukri_cookies():
        p = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "naukri_session.json")
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
        return None
    def get_naukri_session_path():
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "naukri_session.json")


def search_naukri_jobs(role: str, city: str = "bengaluru", limit: int = 5) -> List[Dict]:
    try:
        from playwright.sync_api import sync_playwright

        role_slug = role.lower().strip().replace(" ", "-")
        city_slug = city.lower().strip().replace(" ", "-")
        url = f"https://www.naukri.com/{role_slug}-jobs-in-{city_slug}"
        jobs = []

        cookies = load_naukri_cookies()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )

            if cookies:
                try:
                    context.add_cookies(cookies)
                except Exception as ce:
                    print(f"[Naukri Tool] Cookie notice: {ce}")

            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)

            cards = page.locator("article.jobTuple, div.cust-job-tuple, .srp-jobtuple-wrapper, div[class*='styles_job-tuple-container']").all()

            for card in cards[:limit]:
                try:
                    title_el = card.locator("a.title, a[title]").first
                    company_el = card.locator("a.comp-name, .companyInfo a, a.subTitle").first
                    exp_el = card.locator(".expwdth, .exp-wrap, span[class*='expwdth']").first
                    sal_el = card.locator(".salwdth, .sal-wrap, span[class*='sal']").first
                    loc_el = card.locator(".locwdth, .loc-wrap, span[class*='loc']").first
                    desc_el = card.locator(".job-desc, .ellipsis").first

                    title = title_el.inner_text(timeout=1000) if title_el.count() > 0 else "Tech Role"
                    company = company_el.inner_text(timeout=1000) if company_el.count() > 0 else "Hiring Company"
                    link = title_el.get_attribute("href", timeout=1000) if title_el.count() > 0 else url
                    exp = exp_el.inner_text(timeout=1000) if exp_el.count() > 0 else None
                    sal = sal_el.inner_text(timeout=1000) if sal_el.count() > 0 else None
                    loc = loc_el.inner_text(timeout=1000) if loc_el.count() > 0 else city.capitalize()
                    desc = desc_el.inner_text(timeout=1000) if desc_el.count() > 0 else ""

                    if link and not link.startswith("http"):
                        link = f"https://www.naukri.com{link}"

                    jobs.append({
                        "platform": "Naukri",
                        "title": title.strip(),
                        "company": company.strip(),
                        "location": loc.strip(),
                        "experience": exp.strip() if exp else None,
                        "salary": sal.strip() if sal else None,
                        "url": link,
                        "snippet": desc.strip()[:300],
                        "source": "live_naukri"
                    })
                except Exception:
                    continue
            browser.close()
        return jobs

    except ImportError:
        return [{"error": "Playwright not installed. Run: uv run --with playwright"}]
    except Exception as e:
        return [{"error": f"Naukri scrape failed for '{city}': {str(e)}"}]


def search_naukri_multi_city(role: str, cities: List[str], limit: int = 6) -> List[Dict]:
    all_jobs = []
    per_city = max(2, limit // max(1, len(cities)))
    for city in cities:
        city_jobs = search_naukri_jobs(role=role, city=city, limit=per_city)
        real_jobs = [j for j in city_jobs if "error" not in j]
        all_jobs.extend(real_jobs)
        if len(all_jobs) >= limit:
            break
    return all_jobs[:limit]
