import os
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.db.database import init_db
from backend.app.api import chat, sessions, resume, jobs, auth

def ensure_xvfb():
    """Ensures Xvfb :99 is alive and cleans any stale locks from previous restarts."""
    try:
        # Check if Xvfb process is currently running
        running = False
        if os.path.exists('/proc'):
            for pid in os.listdir('/proc'):
                if pid.isdigit():
                    try:
                        with open(f'/proc/{pid}/cmdline', 'r') as f:
                            cmd = f.read()
                            if 'Xvfb' in cmd and ':99' in cmd:
                                running = True
                                break
                    except Exception:
                        pass
        if not running:
            # Clean stale locks
            for lock_file in ["/tmp/.X99-lock", "/tmp/.X11-unix/X99"]:
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                    except Exception:
                        pass
            subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24", "-ac"])
            print("[Startup] Xvfb display :99 started fresh.")
        else:
            print("[Startup] Xvfb display :99 is already running.")
    except Exception as e:
        print(f"[Startup Xvfb Warning] {e}")

    os.environ["DISPLAY"] = ":99"

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_xvfb()

    print("[Startup] Initializing Database...")
    await init_db()
    print("[Startup] Database ready.")
    yield
    print("[Shutdown] Cleaning up...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(resume.router, prefix=settings.API_V1_STR)
app.include_router(jobs.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "ollama_host": settings.OLLAMA_HOST
    }
