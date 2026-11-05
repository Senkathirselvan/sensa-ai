import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.api.routes import router as apply_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Initializing Sensa AI Job Apply Agent (Agent 3) on port 8002...")
    await init_db()
    yield
    print("🛑 Shutting down Job Apply Agent...")

app = FastAPI(
    title="Sensa AI - Autonomous Job Apply Agent",
    description="Playwright Stealth browser automation, adaptive form filling, and human-in-the-loop application execution.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend studio access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Application routes
app.include_router(apply_router)

@app.get("/")
async def root():
    return {
        "agent": "job-apply-agent",
        "port": settings.PORT,
        "status": "online",
        "description": "Autonomous browser application agent with stealth execution & human-in-the-loop gates."
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "job-apply-agent", "port": settings.PORT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

