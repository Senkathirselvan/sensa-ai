import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings(BaseSettings):
    PORT: int = 8002
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/apply_audit.db"

    # Inter-Agent Service URLs
    JOB_FIND_AGENT_URL: str = os.getenv("JOB_FIND_AGENT_URL", "http://localhost:8000")
    RESUME_PREP_AGENT_URL: str = os.getenv("RESUME_PREP_AGENT_URL", "http://localhost:8001")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3001")

    # LLM Settings for Screening Answers & Vision
    DEFAULT_MODEL: str = "auto"
    NVIDIA_API_KEY: Optional[str] = os.getenv("NVIDIA_API_KEY", None)
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

    # Browser Execution & Stealth Settings
    BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() in ("true", "1", "yes")
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))

    # File Paths
    BASE_DIR: str = BASE_DIR
    SESSIONS_DIR: str = os.getenv("SESSIONS_DIR", os.path.join(BASE_DIR, "data", "sessions"))
    SCREENSHOTS_DIR: str = os.getenv("SCREENSHOTS_DIR", os.path.join(BASE_DIR, "data", "screenshots"))
    RESUME_EXPORTS_DIR: str = os.getenv("RESUME_EXPORTS_DIR", "/home/senkathir-selvan/resume-prep-agent/data/exports")

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure required runtime directories exist
os.makedirs(settings.SESSIONS_DIR, exist_ok=True)
os.makedirs(settings.SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.BASE_DIR, "data"), exist_ok=True)

