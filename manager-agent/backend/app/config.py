import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PORT: int = 8005
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"

    # Worker Agent Endpoints
    JOB_FIND_AGENT_URL: str = "http://localhost:8000"
    RESUME_PREP_AGENT_URL: str = "http://localhost:8001"
    JOB_APPLY_AGENT_URL: str = "http://localhost:8002"
    FRONTEND_URL: str = "http://localhost:3001"

    # AI Model Configuration
    DEFAULT_MODEL: str = "auto"
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_ROUTER_MODEL: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    NVIDIA_CHAT_MODEL: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"

    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:latest"

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://jobagent:jobagent_secret@localhost:5432/jobagent_db"
    SQLITE_URL: str = "sqlite+aiosqlite:///./data/manager.db"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

