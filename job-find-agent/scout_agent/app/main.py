"""
Scout Agent Microservice API
Port: 8001
Endpoints:
  - POST /task: Executes LangGraph Scout workflow
  - GET  /health: Health check endpoint
"""
import sys
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Ensure job-agent root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from shared.schemas import (
    ScoutTaskRequest,
    ScoutTaskResponse,
    ScoutTaskResult,
    TaskStatus,
    JobSpec
)
from scout_agent.app.graph import scout_graph

app = FastAPI(
    title="Job-Finding Agent (Scout)",
    description="Autonomous job discovery, multi-source scraping, and LLM matching microservice.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "agent": "scout_agent",
        "version": "1.0.0",
        "port": 8001
    }


@app.post("/task", response_model=ScoutTaskResponse)
async def execute_scout_task(request: ScoutTaskRequest):
    """
    Executes a job search task requested by the Manager Agent.
    """
    payload = request.payload

    # Prepare LangGraph initial state
    initial_state = {
        "role": payload.role,
        "location": payload.location,
        "cities": payload.cities or [],
        "limit": payload.limit,
        "resume_text": payload.resume_text,
    }

    try:
        # Run through LangGraph pipeline
        final_state = await scout_graph.ainvoke(initial_state)

        raw_jobs = final_state.get("final_jobs", [])
        job_specs = [JobSpec(**job) for job in raw_jobs]

        result = ScoutTaskResult(
            total_found=final_state.get("total_found", len(job_specs)),
            returned_count=len(job_specs),
            jobs=job_specs
        )

        return ScoutTaskResponse(
            task_id=request.task_id,
            status=TaskStatus.COMPLETED,
            agent="scout_agent",
            result=result
        )

    except Exception as e:
        return ScoutTaskResponse(
            task_id=request.task_id,
            status=TaskStatus.FAILED,
            agent="scout_agent",
            error=str(e)
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
