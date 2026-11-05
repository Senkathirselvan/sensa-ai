import os
import json
import time
from typing import Dict, List, Optional
from backend.app.config import settings

class SessionStore:
    """Manages persistent browser cookies and authentication sessions."""

    @staticmethod
    def get_session_file_path(platform: str) -> str:
        clean_name = platform.lower().strip()
        return os.path.join(settings.SESSIONS_DIR, f"{clean_name}_session.json")

    @classmethod
    def is_session_valid(cls, platform: str, cookies: List[Dict]) -> bool:
        """Validates that session cookies are not expired."""
        if not cookies or not isinstance(cookies, list):
            return False

        now = time.time()
        plat = platform.lower().strip()
        cookie_map = {c.get("name"): c for c in cookies if isinstance(c, dict)}

        if plat == "naukri":
            # Check critical Naukri session cookies
            # nauk_rt is the long-lived refresh token (valid for ~1 year)
            # nauk_at is the short-lived access token (~1 hour)
            nauk_rt = cookie_map.get("nauk_rt")
            if nauk_rt:
                exp = nauk_rt.get("expires", -1)
                if exp and 0 < exp < now:
                    return False
                return True

            auth_cookie = cookie_map.get("nauk_at") or cookie_map.get("is_login")
            if not auth_cookie:
                return False
            exp = auth_cookie.get("expires", -1)
            if exp and 0 < exp < now:
                return False
            return True

        elif plat == "linkedin":
            li_at = cookie_map.get("li_at")
            if not li_at:
                return False
            exp = li_at.get("expires", -1)
            if exp and 0 < exp < now:
                return False

        # Generic expiration check: if all expiring cookies are in the past
        expiring = [c for c in cookies if isinstance(c, dict) and c.get("expires", -1) and c.get("expires", -1) > 0]
        if expiring and all(c.get("expires") < now for c in expiring):
            return False

        return True

    @classmethod
    def load_session(cls, platform: str) -> Optional[List[Dict]]:
        """Loads cookies for a specific platform from local or Agent 1 session directory."""
        plat = platform.lower().strip()
        path = cls.get_session_file_path(plat)
        
        # Fallback to Agent 1 (job-find-agent) session directory or backups if available
        agent1_path = f"/home/senkathir-selvan/job-find-agent/data/{plat}_session.json"
        bak_path = f"{path}.bak"
        agent1_bak_path = f"{agent1_path}.bak"

        if not os.path.exists(path):
            if os.path.exists(agent1_path):
                path = agent1_path
            elif os.path.exists(bak_path):
                path = bak_path
            elif os.path.exists(agent1_bak_path):
                path = agent1_bak_path

            # Auto-sync restored file into job-apply-agent data/sessions
            if os.path.exists(path):
                try:
                    os.makedirs(settings.SESSIONS_DIR, exist_ok=True)
                    import shutil
                    target_dest = cls.get_session_file_path(plat)
                    if path != target_dest:
                        shutil.copyfile(path, target_dest)
                except Exception:
                    pass

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cookies = None
                    if isinstance(data, list):
                        cookies = data
                    elif isinstance(data, dict) and "cookies" in data:
                        cookies = data["cookies"]

                    if cookies and cls.is_session_valid(plat, cookies):
                        return cookies
                    else:
                        print(f"[SessionStore] Session for {platform} at {path} is expired or invalid. Bypassing.")
                        return None
            except Exception as e:
                print(f"[SessionStore] Error loading session for {platform}: {e}")
        return None

    @classmethod
    def save_session(cls, platform: str, cookies: List[Dict]) -> bool:
        """Persists session cookies to JSON file."""
        os.makedirs(settings.SESSIONS_DIR, exist_ok=True)
        path = cls.get_session_file_path(platform)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2)
            # Write backup copy
            with open(f"{path}.bak", "w", encoding="utf-8") as f_bak:
                json.dump(cookies, f_bak, indent=2)

            # Also mirror session to job-find-agent data directory so Agent 1 (search scraper) has direct access
            try:
                agent1_data_dir = "/home/senkathir-selvan/job-find-agent/data"
                if os.path.exists(agent1_data_dir):
                    agent1_session_file = os.path.join(agent1_data_dir, f"{platform.lower().strip()}_session.json")
                    with open(agent1_session_file, "w", encoding="utf-8") as f_a1:
                        json.dump(cookies, f_a1, indent=2)
                    with open(f"{agent1_session_file}.bak", "w", encoding="utf-8") as f_a1_bak:
                        json.dump(cookies, f_a1_bak, indent=2)
            except Exception as e_a1:
                print(f"[SessionStore] Error mirroring session to job-find-agent: {e_a1}")

            return True
        except Exception as e:
            print(f"[SessionStore] Error saving session for {platform}: {e}")
            return False

    @classmethod
    def is_session_available(cls, platform: str) -> bool:
        cookies = cls.load_session(platform)
        return bool(cookies and len(cookies) > 0)

    @classmethod
    def delete_session(cls, platform: str) -> bool:
        plat = platform.lower().strip()
        path = cls.get_session_file_path(plat)
        deleted = False
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted = True
            except Exception as e:
                print(f"[SessionStore] Error deleting session {path}: {e}")
        agent1_path = f"/home/senkathir-selvan/job-find-agent/data/{plat}_session.json"
        if os.path.exists(agent1_path):
            try:
                os.remove(agent1_path)
                deleted = True
            except Exception:
                pass
        return deleted


