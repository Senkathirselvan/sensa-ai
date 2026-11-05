import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.db.database import init_db
from backend.app.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 Initializing Sensa AI Resume Preparation Agent on port {settings.PORT}...")
    await init_db()
    yield
    print("🛑 Shutting down Resume Preparation Agent...")

app = FastAPI(
    title="Sensa AI - Resume Preparation Agent",
    version="1.0.0",
    description="Autonomous ATS Resume Tailoring, STAR/XYZ Bullet Reframing, and Multi-Format PDF/DOCX Generation",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
async def root():
    return {
        "service": "Sensa AI - Resume Preparation Agent (Agent 2)",
        "status": "online",
        "docs": "/docs",
        "stream_endpoint": "/api/resume/tailor/stream"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)

