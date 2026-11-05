# 💼 Local AI Job Search & Apply Agent (Enterprise Edition)

A 100% local, autonomous AI Agent that discovers, analyzes, scores, and prepares applications for tech jobs across LinkedIn, Indeed, and Naukri.

Built with an enterprise-caliber **ChatGPT / Claude style React 18 frontend**, **FastAPI Server-Sent Events (SSE) streaming backend**, **PostgreSQL database**, and containerized with **Docker Compose**.

---

## 🌟 Key Features

1. **ChatGPT & Claude Quality UI (React 18 + Tailwind CSS)**:
   - **Conversation History**: Multi-session management categorized into *Today*, *Yesterday*, *Previous 7 Days*, and *Older*.
   - **Real-Time Token Streaming**: Real-time token by token responses with typing indicators.
   - **Visual Agent Step Badges**: Expandable live status badges (e.g. `🔍 Searching LinkedIn & Indeed...`, `📄 Reading resume.pdf...`, `🧠 Scoring 6 jobs against resume...`).
   - **Interactive Job Cards**: 0–100 match percentage gauges, matched vs missing skills chips, and one-click save / apply buttons.
   - **Antigravity-Style Chat Dock**: Sleek bottom input bar with `+` attachment button (modal for uploading PDF/DOCX resumes, photos, or switching models).
   - **Human-in-the-Loop Apply**: Opens application links in a browser only after candidate confirmation.

2. **FastAPI & Async ReAct Agent**:
   - Server-Sent Events (`/api/chat/stream`) yielding live tokens, statuses, and structured job payloads.
   - Resume parser extracting candidate skills and experience using local Ollama.
   - Automated city planning and job scraping via Python-JobSpy and Playwright.

3. **Multi-Container Docker Architecture**:
   - `frontend`: React 18 + Vite served by high-performance Nginx on port `3000`.
   - `backend`: FastAPI Python 3.11 service on port `8000`.
   - `db`: PostgreSQL 16 on port `5432` with persistent Docker volume.
   - Host Ollama bridge via `host.docker.internal:11434`.

---

## 🚀 Quickstart with Docker Compose

Ensure Ollama is running on your host machine:
```bash
ollama serve
ollama pull qwen2.5
```

Build and launch all 3 containers with a single command:
```bash
docker compose up --build
```

Access the application in your browser:
- 🌐 **Web UI**: [http://localhost:3000](http://localhost:3000)
- 🔌 **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 🗄️ **PostgreSQL**: `localhost:5432` (User: `jobagent`, DB: `jobagent_db`)

---

## 💻 Standalone Local Development (Without Docker)

### 1. Backend (FastAPI)
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn backend.app.main:app --reload --port 8000
```

### 2. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

