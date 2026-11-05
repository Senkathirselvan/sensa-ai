import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("manager_agent.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info(f"🚀 Sensa AI Executive Manager Agent starting on port {settings.PORT}...")
    logger.info(f"   • Job Find Worker:    {settings.JOB_FIND_AGENT_URL}")
    logger.info(f"   • Resume Prep Worker: {settings.RESUME_PREP_AGENT_URL}")
    logger.info(f"   • Job Apply Worker:   {settings.JOB_APPLY_AGENT_URL}")
    logger.info("=" * 60)
    yield
    logger.info("🛑 Sensa AI Executive Manager Agent shutting down.")

app = FastAPI(
    title="Sensa AI - Executive Manager Agent",
    description="Multi-agent Orchestrator & Router managing job-find-agent, resume-prep-agent, and job-apply-agent.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

