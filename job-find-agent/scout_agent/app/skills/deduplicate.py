"""
Skill: Deduplicator
Cleans URLs and removes duplicate job postings using fuzzy hash matching.
"""
import hashlib
import re
import urllib.parse
from typing import List, Dict, Any


def normalize_url(url: str) -> str:
    """Removes tracking query parameters from job URLs."""
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    # Strip tracking query parameters
    filtered_queries = []
    for q in parsed.query.split("&"):
        if not any(q.lower().startswith(p) for p in ["utm_", "ref", "trk", "tracking", "sp"]):
            filtered_queries.append(q)
    clean_query = "&".join(filter(None, filtered_queries))
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, ""))


def deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters duplicate jobs based on URL and normalized (company + title) hash."""
    seen_hashes = set()
    seen_urls = set()
    unique_jobs = []

    for job in jobs:
        url = normalize_url(job.get("url", ""))
        title = re.sub(r"[^a-zA-Z0-9]", "", job.get("title", "").lower())
        company = re.sub(r"[^a-zA-Z0-9]", "", job.get("company", "").lower())

        content_key = f"{company}_{title}"
        content_hash = hashlib.sha256(content_key.encode()).hexdigest()

        if url and url in seen_urls:
            continue
        if content_hash in seen_hashes:
            continue

        if url:
            seen_urls.add(url)
        seen_hashes.add(content_hash)

        # Update job with cleaned URL
        job["url"] = url or job.get("url", "")
        unique_jobs.append(job)

    return unique_jobs
