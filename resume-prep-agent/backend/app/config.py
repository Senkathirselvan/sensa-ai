import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings(BaseSettings):
    PORT: int = 8001
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_agent"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/job_agent"
    SQLITE_FALLBACK_URL: str = "sqlite+aiosqlite:///./data/resume_agent.db"
    
    # Agent 1 Integration
    JOB_AGENT_URL: str = "http://localhost:8000"
    
    # AI Models
    DEFAULT_MODEL: str = "auto"
    NVIDIA_API_KEY: Optional[str] = os.getenv("NVIDIA_API_KEY", None)
    NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:latest"
    
    # File Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    MASTER_RESUME_DIR: str = os.path.join(BASE_DIR, "data", "master")
    EXPORTS_DIR: str = os.path.join(BASE_DIR, "data", "exports")
    
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Ensure required directories exist
os.makedirs(settings.MASTER_RESUME_DIR, exist_ok=True)
os.makedirs(settings.EXPORTS_DIR, exist_ok=True)

