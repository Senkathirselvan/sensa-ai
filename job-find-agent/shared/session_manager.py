"""
Universal Session & Cookie Manager for Job Platforms (Naukri, LinkedIn, Indeed).
Handles:
  - Cookie sanitization (adapting browser-extension exports to Playwright's strict schema)
  - Cookie loading & saving from standard paths
  - Session verification & health check
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("session_manager")

DEFAULT_CANDIDATE_PATHS = [
    os.getenv("NAUKRI_SESSION_PATH"),
    "/app/data/naukri_session.json",
    "/home/senkathir-selvan/job-apply-agent/data/sessions/naukri_session.json",
    "/home/senkathir-selvan/job-find-agent/data/naukri_session.json",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "naukri_session.json"),
    os.path.join(os.getcwd(), "data", "naukri_session.json"),
    os.path.join(os.getcwd(), "naukri_session.json"),
]


def get_naukri_session_path() -> str:
    """Returns the most appropriate path for naukri_session.json."""
    for path in DEFAULT_CANDIDATE_PATHS:
        if path and os.path.exists(path):
            return path
    # If not exists yet, return default data/ path
    repo_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(repo_data, exist_ok=True)
    return os.path.join(repo_data, "naukri_session.json")


def sanitize_cookie(c: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Sanitizes an individual cookie dictionary to match Playwright's required schema.
    Strips invalid extension metadata (hostOnly, session, storeId) and normalizes sameSite.
    """
    name = c.get("name")
    value = c.get("value")
    if not name or value is None:
        return None

    sanitized = {
        "name": str(name),
        "value": str(value),
        "path": c.get("path", "/"),
    }

    # Domain
    domain = c.get("domain")
    if domain:
        # Strip leading dot if solitary or invalid
        sanitized["domain"] = domain
    else:
        sanitized["domain"] = ".naukri.com"

    # Expiry / Expires
    expires = c.get("expires") or c.get("expirationDate")
    if expires is not None:
        try:
            sanitized["expires"] = float(expires)
        except (ValueError, TypeError):
            pass

    # HttpOnly & Secure
    if "httpOnly" in c:
        sanitized["httpOnly"] = bool(c["httpOnly"])
    if "secure" in c:
        sanitized["secure"] = bool(c["secure"])

    # SameSite must be strictly 'Strict', 'Lax', or 'None'
    same_site = c.get("sameSite")
    if same_site:
        s_lower = str(same_site).lower()
        if "strict" in s_lower:
            sanitized["sameSite"] = "Strict"
        elif "lax" in s_lower:
            sanitized["sameSite"] = "Lax"
        elif "none" in s_lower or "no_restriction" in s_lower:
            sanitized["sameSite"] = "None"
        # If unspecified or invalid, omit sameSite field so Playwright defaults safely

    return sanitized


def sanitize_cookies_list(cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitizes a list of cookies."""
    cleaned = []
    for c in cookies:
        if isinstance(c, dict):
            sc = sanitize_cookie(c)
            if sc:
                cleaned.append(sc)
    return cleaned


def load_naukri_cookies() -> Optional[List[Dict[str, Any]]]:
    """Loads and sanitizes Naukri session cookies if file exists."""
    path = get_naukri_session_path()
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Some exports wrap cookies in a key {"cookies": [...]}
        raw_cookies = data.get("cookies", data) if isinstance(data, dict) else data

        if isinstance(raw_cookies, list) and len(raw_cookies) > 0:
            return sanitize_cookies_list(raw_cookies)
    except Exception as e:
        logger.warning(f"Failed to load cookies from {path}: {e}")

    return None


def save_naukri_cookies(cookies: List[Dict[str, Any]], target_path: Optional[str] = None) -> str:
    """Saves sanitized cookies to JSON file."""
    path = target_path or get_naukri_session_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    sanitized = sanitize_cookies_list(cookies)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)

    return path
