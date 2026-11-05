import sys
import os
SHARED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../shared'))
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)
try:
    from session_manager import load_naukri_cookies
except Exception:
    def load_naukri_cookies():
        return None
import json
import os
import re
import asyncio
import httpx
from typing import AsyncGenerator, List, Dict, Any, Optional
from google import genai
from google.genai import types
from backend.app.core.config import settings
from backend.app.agent.prompt import get_system_prompt
from backend.app.agent.memory import manage_context
from backend.app.services.resume_service import read_resume_text as svc_read_resume_text
from backend.app.services.search_service import search_web_jobs as svc_search_web_jobs
from backend.app.services.naukri_service import search_naukri_jobs as svc_search_naukri_jobs, search_naukri_multi_city as svc_search_naukri_multi_city
from backend.app.services.scorer_service import score_and_rank_jobs as svc_score_and_rank_jobs, normalize_platform as svc_normalize_platform
from backend.app.services.apply_service import (
    queue_job_for_apply as svc_queue_job_for_apply,
    get_applied_jobs as svc_get_applied_jobs,
    get_saved_jobs as svc_get_saved_jobs,
    get_interview_jobs as svc_get_interview_jobs
)

async def svc_prepare_tailored_resume(job_title: str, company: str, job_description: str = "", target_pages: int = 2) -> dict:
    """Invokes Resume Preparation Agent to tailor and compile 2-page A4 resume and evaluate ATS match."""
    endpoints = [
        "http://host.docker.internal:8001/api/resume/tailor/stream",
        "http://172.17.0.1:8001/api/resume/tailor/stream",
        "http://localhost:8001/api/resume/tailor/stream"
    ]
    payload = {
        "job_title": job_title,
        "company": company,
        "job_description": job_description or f"{job_title} at {company}",
        "target_pages": target_pages
    }
    custom_timeout = httpx.Timeout(120.0, connect=10.0, read=120.0)

    for url in endpoints:
        try:
            async with httpx.AsyncClient(timeout=custom_timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    if resp.status_code != 200:
                        continue
                    tailored_result = None
                    async for line in resp.aiter_lines():
                        if line.startswith("data:"):
                            payload_str = line[5:].strip()
                            try:
                                parsed = json.loads(payload_str)
                                if isinstance(parsed, dict) and "tailored_score" in parsed:
                                    tailored_result = parsed
                            except Exception:
                                pass
                    if tailored_result:
                        return {
                            "status": "success",
                            "job_title": job_title,
                            "company": company,
                            "original_score": tailored_result.get("original_score"),
                            "tailored_score": tailored_result.get("tailored_score"),
                            "matched_keywords": tailored_result.get("matched_keywords", []),
                            "missing_keywords": tailored_result.get("missing_keywords", []),
                            "pdf_filename": tailored_result.get("pdf_filename"),
                            "html_filename": tailored_result.get("html_filename"),
                            "docx_filename": tailored_result.get("docx_filename"),
                            "markdown_content": tailored_result.get("markdown_content"),
                            "pdf_url": f"/api/resume/download/{tailored_result.get('pdf_filename')}",
                            "preview_url": f"/api/resume/preview/{tailored_result.get('html_filename')}",
                            "docx_url": f"/api/resume/download/{tailored_result.get('docx_filename')}"
                        }
        except Exception:
            continue
    return {
        "status": "error",
        "message": "Resume Preparation Agent service unavailable on port 8001."
    }

# ── Unified Tool Schemas ───────────────────────────────────────────────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_naukri_jobs",
            "description": "Scrapes live jobs from Naukri.com for specific Indian cities or nationwide, with freshness filtering by days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Job title or role to search."},
                    "location": {"type": "string", "description": "Location or city (e.g. 'India', 'Chennai', 'Bengaluru'). Default is 'India'."},
                    "limit": {"type": "integer", "description": "Max results to return (default 6)."},
                    "days": {"type": "integer", "description": "Filter for jobs posted within the last N days (e.g. 1, 3, 5, 7, 15)."}
                },
                "required": ["role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_my_resume",
            "description": "Reads the user's uploaded local resume ('resume.pdf'). STRICT: ONLY call this if the user explicitly asks to read/analyze their resume or evaluate their background in their current prompt.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web_jobs",
            "description": "Searches for live tech job postings from LinkedIn and Indeed with freshness filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "The job title, e.g. 'Python Backend Developer'."},
                    "location": {"type": "string", "description": "Location, e.g. 'India', 'Bengaluru', or 'Remote'."},
                    "limit": {"type": "integer", "description": "Max results to return (default 6)."},
                    "days": {"type": "integer", "description": "Filter for jobs posted within the last N days (e.g. 1, 3, 5, 7, 15)."}
                },
                "required": ["role"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_and_rank_jobs",
            "description": "Scores a list of job postings (0-100 match percentage) against the candidate's resume. ONLY call this if the user explicitly requests resume scoring or matching. Pass the existing job objects preserving their title, company, platform, location, posted_date, and url.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jobs": {"type": "array", "items": {"type": "object"}, "description": "List of job objects to score. Must preserve title, company, platform, url, location, and posted_date."}
                },
                "required": ["jobs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "queue_job_for_apply",
            "description": "Queues a selected job for application with human-in-the-loop confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job": {"type": "object", "description": "The full job object to apply for."}
                },
                "required": ["job"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_tailored_resume",
            "description": "Prepares and compiles a complete, ATS-optimized 2-page A4 resume using the executive template, audits ATS keyword density and match score, and produces downloadable PDF/HTML files with zero empty spaces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {"type": "string", "description": "The target job title (e.g. 'Backend Python Developer')."},
                    "company": {"type": "string", "description": "The hiring company name (e.g. 'Tekskills India Pvt Ltd')."},
                    "job_description": {"type": "string", "description": "The job description or responsibilities and required tech stack."},
                    "target_pages": {"type": "integer", "description": "Target pages (default: 2).", "default": 2}
                },
                "required": ["job_title", "company"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_applied_jobs",
            "description": "Retrieves the candidate's list of applied jobs from the application tracker and apply agent, including direct platform URLs, submission verification statuses, timestamps, and proof screenshot links.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_saved_jobs",
            "description": "Retrieves the candidate's list of saved/bookmarked jobs from the database tracker (status == 'SAVED'). Call this whenever the user asks to see, check, or list their saved or bookmarked jobs.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_interview_jobs",
            "description": "Retrieves the candidate's list of jobs where an interview has been scheduled (status == 'INTERVIEW'). Call this when the user asks about interview scheduled jobs.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# Tool schemas converted for Claude (Anthropic)
CLAUDE_TOOLS = [
    {
        "name": t["function"]["name"],
        "description": t["function"]["description"],
        "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}})
    }
    for t in TOOL_SCHEMAS
]

# Python tool definitions for Google GenAI SDK
def read_my_resume() -> str:
    """Reads and extracts skills, experience, and target roles from the user's uploaded local resume."""
    return ""

def search_web_jobs(role: str, location: str = "India", limit: int = 6, days: int = None) -> list:
    """Searches live tech job listings across LinkedIn, Indeed, etc., with optional freshness days."""
    return []

def search_naukri_jobs(role: str, location: str = "India", limit: int = 6, days: int = None) -> list:
    """Scrapes live jobs from Naukri.com for specific Indian cities or nationwide, with freshness days filter."""
    return []

def score_and_rank_jobs(jobs: list[dict]) -> list:
    """Scores a list of job postings (0-100 match percentage) against the candidate's resume."""
    return []

def queue_job_for_apply(job: dict) -> dict:
    """Queues a selected job for application with human-in-the-loop confirmation."""
    return {}

def prepare_tailored_resume(job_title: str, company: str, job_description: str = "", target_pages: int = 2) -> dict:
    """Prepares and compiles a complete, ATS-optimized 2-page A4 resume using the executive template, audits ATS keyword density and match score, and produces downloadable PDF/HTML files."""
    return {}

def get_applied_jobs() -> list:
    """Retrieves the candidate's applied jobs history, direct portal links, and proof screenshots."""
    return []

def get_saved_jobs() -> list:
    """Retrieves the candidate's saved/bookmarked jobs from the job tracker."""
    return []

def get_interview_jobs() -> list:
    """Retrieves the candidate's interview scheduled jobs from the job tracker."""
    return []

GEMINI_TOOLS = [search_naukri_jobs, search_web_jobs, read_my_resume, score_and_rank_jobs, queue_job_for_apply, prepare_tailored_resume, get_applied_jobs, get_saved_jobs, get_interview_jobs]

async def execute_tool(
    name: str,
    args: dict,
    collected_jobs: list,
    model: str,
    user_inferred_days: int = None,
    user_wants_resume: bool = False,
    is_job_search_intent: bool = False,
    google_key: Optional[str] = None,
    claude_key: Optional[str] = None
) -> Any:
    if name == "read_my_resume":
        if is_job_search_intent and not user_wants_resume:
            return "Direct job search requested. Skipped reading resume."
        return svc_read_resume_text()
    elif name == "search_web_jobs":
        role = args.get("role", "Software Engineer")
        location = args.get("location", "India")
        limit = args.get("limit", 6)
        days = args.get("days") or user_inferred_days
        results = await svc_search_web_jobs(role=role, location=location, limit=limit, days=days)
        collected_jobs.extend(results)
        # Return compact payload to the LLM to conserve prompt tokens
        return [
            {
                "title": j.get("title"),
                "company": j.get("company"),
                "location": j.get("location"),
                "posted_date": j.get("posted_date"),
                "url": j.get("url"),
                "platform": svc_normalize_platform(j)
            }
            for j in results
        ]
    elif name == "search_naukri_jobs":
        role = args.get("role", "Software Engineer")
        raw_loc = args.get("location")
        raw_cities = args.get("cities")
        if raw_loc:
            location = raw_loc
        elif isinstance(raw_cities, list) and raw_cities:
            location = raw_cities[0]
        elif isinstance(raw_cities, str) and raw_cities:
            location = raw_cities
        else:
            location = "India"
        limit = args.get("limit", 6)
        days = args.get("days") or user_inferred_days
        results = await svc_search_naukri_jobs(role=role, location=location, limit=limit, days=days)
        collected_jobs.extend(results)
        return [
            {"title": j.get("title"), "company": j.get("company"), "location": j.get("location"), "posted_date": j.get("posted_date"), "url": j.get("url"), "platform": "Naukri"}
            for j in results
        ]
    elif name == "score_and_rank_jobs":
        if not user_wants_resume:
            return {"status": "skipped", "message": "Direct job search requested. Skipped resume scoring."}
        jobs_to_score = args.get("jobs") or collected_jobs
        scored = await svc_score_and_rank_jobs(jobs_to_score, model=model, google_key=google_key, claude_key=claude_key)
        
        for s in scored:
            s["platform"] = svc_normalize_platform(s)

        if not collected_jobs:
            for s in scored:
                collected_jobs.append(s)
        else:
            for s in scored:
                matched_idx = -1
                for idx, existing in enumerate(collected_jobs):
                    existing["platform"] = svc_normalize_platform(existing)
                    same_url = (existing.get("url") and s.get("url") and existing.get("url").strip() == s.get("url").strip())
                    same_title_co = (
                        existing.get("title", "").strip().lower() == s.get("title", "").strip().lower() and
                        existing.get("company", "").strip().lower() == s.get("company", "").strip().lower()
                    )
                    if same_url or same_title_co:
                        matched_idx = idx
                        break
                if matched_idx >= 0:
                    collected_jobs[matched_idx] = {
                        **collected_jobs[matched_idx],
                        **s,
                        "platform": svc_normalize_platform(collected_jobs[matched_idx]) if svc_normalize_platform(collected_jobs[matched_idx]) != "Web" else svc_normalize_platform(s)
                    }
                else:
                    collected_jobs.append(s)

        for j in collected_jobs:
            j["platform"] = svc_normalize_platform(j)
        # Return compact scores to save LLM tokens
        return [
            {
                "title": j.get("title"),
                "company": j.get("company"),
                "score": j.get("score"),
                "match_reasons": j.get("match_reasons", [])[:2],
                "missing_skills": j.get("missing_skills", [])[:2]
            }
            for j in scored
        ]
    elif name == "queue_job_for_apply":
        job = args.get("job", {})
        return svc_queue_job_for_apply(job)
    elif name == "prepare_tailored_resume":
        job_title = args.get("job_title", "Backend Python Developer")
        company = args.get("company", "Target Company")
        job_description = args.get("job_description", "")
        target_pages = args.get("target_pages", 2)
        return await svc_prepare_tailored_resume(job_title, company, job_description, target_pages)
    elif name == "get_applied_jobs":
        results = await svc_get_applied_jobs()
        collected_jobs.extend(results)
        return results
    elif name == "get_saved_jobs":
        results = await svc_get_saved_jobs()
        collected_jobs.extend(results)
        return results
    elif name == "get_interview_jobs":
        results = await svc_get_interview_jobs()
        collected_jobs.extend(results)
        return results
    return f"Unknown tool: {name}"

# ── Provider 0: NVIDIA NIM Turn (Nemotron 3.5 120B Super - Job Find Agent) ────
async def run_nvidia_turn(
    messages: List[Dict],
    system_prompt: str,
    api_key: str,
    base_url: str = "https://integrate.api.nvidia.com/v1",
    model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
) -> Dict[str, Any]:
    """Calls NVIDIA NIM OpenAI-compatible API via async HTTP with reasoning and function calling."""
    nvidia_msgs = []
    
    # Ensure system prompt is present
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        nvidia_msgs.append({"role": "system", "content": system_prompt})

    for m in messages:
        role = m.get("role")
        content = m.get("content")
        tool_calls = m.get("tool_calls")
        tool_call_id = m.get("tool_call_id")
        tool_name = m.get("name")

        if role == "tool":
            nvidia_msgs.append({
                "role": "tool",
                "tool_call_id": tool_call_id or "call_default",
                "name": tool_name or "tool_result",
                "content": content or ""
            })
        elif role == "assistant":
            asst_msg: Dict[str, Any] = {"role": "assistant"}
            asst_msg["content"] = content if content else None
            if tool_calls:
                asst_msg["tool_calls"] = tool_calls
            nvidia_msgs.append(asst_msg)
        elif role == "user":
            user_imgs = m.get("images") or []
            if user_imgs:
                content_parts = []
                if content:
                    content_parts.append({"type": "text", "text": content})
                for img_url in user_imgs:
                    content_parts.append({"type": "image_url", "image_url": {"url": img_url}})
                nvidia_msgs.append({"role": "user", "content": content_parts})
            elif content:
                nvidia_msgs.append({"role": "user", "content": content})
        elif role == "system":
            if content:
                nvidia_msgs.append({"role": role, "content": content})

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": nvidia_msgs,
        "tools": TOOL_SCHEMAS,
        "temperature": 0.2,
        "top_p": 0.95,
        "max_tokens": 4096
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code == 429:
            raise RuntimeError("NVIDIA Rate Limit (429) / Quota Reached")
        if res.status_code != 200:
            raise RuntimeError(f"NVIDIA API Error ({res.status_code}): {res.text}")
        data = res.json()

    choice = data.get("choices", [{}])[0]
    msg = choice.get("message", {})
    return {
        "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "tool_calls": msg.get("tool_calls", []),
        "provider": f"NVIDIA NIM ({model.split('/')[-1]})"
    }

# ── Provider 1: Claude Turn ──────────────────────────────────────────────────
async def run_claude_turn(
    messages: List[Dict],
    system_prompt: str,
    api_key: str
) -> Dict[str, Any]:
    """Calls Anthropic Claude API via async HTTP."""
    claude_msgs = []
    for m in messages:
        role = m.get("role")
        text = (m.get("content") or "").strip()
        if role == "tool":
            claude_msgs.append({"role": "user", "content": f"Tool Result:\n{text}"})
        elif role in ["user", "assistant"] and text:
            claude_msgs.append({"role": role, "content": text})

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": claude_msgs,
        "tools": CLAUDE_TOOLS
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        if res.status_code == 429:
            raise RuntimeError("Claude Rate Limit (429) / Quota Reached")
        if res.status_code != 200:
            raise RuntimeError(f"Claude API Error ({res.status_code}): {res.text}")
        data = res.json()

    text_parts = []
    tool_calls = []
    for item in data.get("content", []):
        if item.get("type") == "text":
            text_parts.append(item.get("text", ""))
        elif item.get("type") == "tool_use":
            tool_calls.append({
                "function": {
                    "name": item.get("name"),
                    "arguments": item.get("input", {})
                }
            })

    return {
        "content": "".join(text_parts),
        "tool_calls": tool_calls,
        "provider": "Claude 3.5 Haiku"
    }

# ── Provider 2: Gemini Turn ──────────────────────────────────────────────────
async def run_gemini_turn(
    messages: List[Dict],
    system_prompt: str,
    api_key: str
) -> Dict[str, Any]:
    """Calls Google Gemini API via official google-genai SDK."""
    client = genai.Client(api_key=api_key)

    contents = []
    for m in messages:
        role = m.get("role")
        text = (m.get("content") or "").strip()
        if not text and role == "assistant":
            text = "[Tool Execution Started]"

        if role in ["user", "tool"]:
            target_role = "user"
            msg_text = f"Tool Result:\n{text}" if role == "tool" else text
        elif role == "assistant":
            target_role = "model"
            msg_text = text
        else:
            continue

        if not msg_text:
            continue

        if contents and contents[-1].role == target_role:
            contents[-1].parts.append(types.Part.from_text(text="\n" + msg_text))
        else:
            contents.append(types.Content(role=target_role, parts=[types.Part.from_text(text=msg_text)]))

    if not contents:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text="Hello, please assist with job search.")])]

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=GEMINI_TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.2,
    )

    models_to_try = [
        "gemini-flash-latest",
        "gemini-3.8-flash",
        "gemini-3.5-flash-lite",
    ]
    response = None
    last_err = None
    used_model = "gemini-flash-latest"

    for target_model in models_to_try:
        try:
            response = await client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            used_model = target_model
            print(f"[GEMINI SUCCESS]: Connected with model {used_model}", flush=True)
            break
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            print(f"[GEMINI MODEL {target_model} FAILED]: {e}", flush=True)
            if any(term in err_str for term in [
                "not found", "404", "503", "unavailable", "high demand",
                "rate limit", "429", "quota", "resource_exhausted",
                "resolution", "connect", "timeout"
            ]):
                await asyncio.sleep(0.5)
                continue
            raise e

    if not response and last_err:
        raise last_err

    tool_calls = []
    if getattr(response, "function_calls", None):
        for fc in response.function_calls:
            tool_calls.append({
                "function": {
                    "name": fc.name,
                    "arguments": dict(fc.args) if fc.args else {}
                }
            })

    content_text = ""
    try:
        content_text = response.text or ""
    except Exception:
        content_text = ""

    return {
        "content": content_text,
        "tool_calls": tool_calls,
        "provider": f"Gemini ({used_model})"
    }

# ── Provider 3: Local Ollama Turn ────────────────────────────────────────────
async def run_ollama_turn(
    messages: List[Dict],
    model: str = "qwen2.5"
) -> Dict[str, Any]:
    """Calls 100% Local Ollama on host machine."""
    async with httpx.AsyncClient(timeout=240.0) as client:
        res = await client.post(
            f"{settings.OLLAMA_HOST}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "tools": TOOL_SCHEMAS,
                "stream": False,
                "keep_alive": "30m"
            }
        )
        if res.status_code != 200:
            raise RuntimeError(f"Ollama Error ({res.status_code}): {res.text}")
        data = res.json()

    msg = data.get("message", {})
    return {
        "content": msg.get("content", ""),
        "tool_calls": msg.get("tool_calls", []),
        "provider": f"Local Ollama ({model})"
    }

# ── 4-Tier Cascading Multi-Provider Engine ─────────────────────────────────────
async def stream_agent_reasoning(
    chat_history: List[Dict],
    model: str = "auto",
    anthropic_key: Optional[str] = None,
    gemini_key: Optional[str] = None,
    nvidia_key: Optional[str] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    4-Tier Cascading Execution (Job Find Agent):
      0. NVIDIA NIM Nemotron 3.5 120B Super (Deep reasoning & thinking tokens)
         └── If quota/limit reached:
      1. Claude 3.5 Haiku (Lightning fast cloud)
         └── If quota/limit reached:
      2. Gemini 1.5 Flash (1,500 requests/day free cloud)
         └── If quota/limit reached:
      3. Local Ollama Qwen 2.5 (100% Free, offline, unlimited bedrock)
    """
    system_prompt = get_system_prompt()
    working_history = list(chat_history)
    if working_history and working_history[0].get("role") == "system":
        working_history[0]["content"] = system_prompt
    else:
        working_history.insert(0, {"role": "system", "content": system_prompt})

    # Fast-path for simple greetings
    last_user_msg = next((m.get("content", "").strip().lower() for m in reversed(working_history) if m.get("role") == "user"), "")
    if last_user_msg in ["hi", "hello", "hey", "hola", "hi there", "hello there", "good morning", "good evening", "greetings"]:
        reply = "Hello! I am your Enterprise AI Assistant. How can I assist you today with coding, technical architecture, or career opportunities?"
        for word in reply.split(" "):
            yield {"type": "token", "data": word + " "}
            await asyncio.sleep(0.015)
        yield {"type": "done", "data": {"content": reply, "job_cards": []}}
        return

    last_user_raw_msg = next((m.get("content", "").strip() for m in reversed(working_history) if m.get("role") == "user"), "")
    clean_user_msg = last_user_raw_msg.lower().strip()

    # Find previous assistant message for context
    asst_messages = [m.get("content", "") for m in working_history if m.get("role") == "assistant" and m.get("content")]
    prev_asst_msg = asst_messages[-1] if asst_messages else ""

    resume_keywords = ["resume", "cv", "score", "match", "my profile", "my background", "rate", "evaluate me"]
    user_wants_resume = any(kw in clean_user_msg for kw in resume_keywords)

    is_affirmative = clean_user_msg in [
        "yes", "yeah", "yep", "sure", "ok", "okay", "yes please", "please do",
        "draft it", "draft cover letter", "queue it", "apply", "go ahead", "do it",
        "yes draft it", "yes please draft", "yes queue it", "yes apply", "y"
    ] or bool(re.match(r'^(yes|sure|okay?|please|draft\s+(?:the\s+)?cover\s+letter|queue\s+(?:the\s+)?job)\b', clean_user_msg))

    offered_cover_letter_or_apply = any(phrase in prev_asst_msg.lower() for phrase in [
        "draft a short cover letter", "draft a cover letter", "queue this job", "help you queue", "cover letter for this application", "queue this job for apply"
    ])

    is_cover_letter_intent = any(kw in clean_user_msg for kw in ["cover letter", "outreach message", "recruiter note"])

    is_saved_jobs_intent = any(kw in clean_user_msg for kw in [
        "saved job", "saved jobs", "show my saved", "show saved", "my saved jobs",
        "bookmarked", "bookmarks", "jobs i saved", "saved list"
    ])

    is_interview_jobs_intent = any(kw in clean_user_msg for kw in [
        "interview job", "interview scheduled", "my interviews", "show my interview",
        "interview jobs", "interview status", "scheduled interview"
    ])

    is_applied_jobs_intent = any(kw in clean_user_msg for kw in [
        "applied job", "applied list", "applied jobs", "application status",
        "show my applied", "show applied", "jobs i applied", "my applications",
        "application tracker", "tracking list", "previously applied", "status tracker"
    ]) and not is_saved_jobs_intent and not is_interview_jobs_intent

    job_search_triggers = [
        "find", "search", "looking for", "jobs", "openings", "vacancies",
        "opportunities", "hiring", "listings", "roles", "positions"
    ]
    is_job_search_intent = (
        any(re.search(r'\b' + re.escape(kw) + r'\b', clean_user_msg) for kw in job_search_triggers)
        and not is_saved_jobs_intent
        and not is_interview_jobs_intent
        and not is_applied_jobs_intent
    )

    if is_saved_jobs_intent:
        working_history.append({
            "role": "user",
            "content": (
                "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user is asking to view their SAVED jobs (bookmarks). "
                "CRITICAL INSTRUCTIONS: "
                "1. You MUST execute the 'get_saved_jobs' tool immediately. "
                "2. DO NOT call 'get_applied_jobs'. DO NOT call 'search_naukri_jobs' or 'search_web_jobs'. "
                "3. If 0 saved jobs are returned, clearly state: 'You currently have 0 saved jobs in your tracker. You can save jobs by clicking the 'Save' button on any job card during your searches.' DO NOT invent jobs or show applied jobs. "
                "4. If saved jobs exist, present them clearly with their Title, Company, Platform, Location, and portal URL."
            )
        })
    elif is_interview_jobs_intent:
        working_history.append({
            "role": "user",
            "content": (
                "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user is asking to view their INTERVIEW scheduled jobs. "
                "CRITICAL INSTRUCTIONS: "
                "1. You MUST execute the 'get_interview_jobs' tool immediately. "
                "2. DO NOT call 'get_applied_jobs'. DO NOT call 'search_naukri_jobs' or 'search_web_jobs'. "
                "3. If 0 interview jobs are returned, clearly state: 'You currently have 0 interview scheduled jobs in your tracker.' "
                "4. If interview jobs exist, present them with their Title, Company, and scheduled details."
            )
        })
    elif is_applied_jobs_intent:
        working_history.append({
            "role": "user",
            "content": (
                "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user is asking to view their applied jobs or application tracker. "
                "CRITICAL INSTRUCTIONS: "
                "1. You MUST execute the 'get_applied_jobs' tool immediately to retrieve the candidate's real applied job records and proof screenshots. "
                "2. DO NOT call 'search_naukri_jobs' or 'search_web_jobs'. "
                "3. Present each applied job with its Company, Job Title, Platform, direct portal link [View on <Platform>](<url>), submission status (e.g. '✓ Submitted & Verified'), applied date, and proof screenshot link [📸 View Proof Screenshot](/api/apply/screenshot/<filename>)."
            )
        })
    elif (is_affirmative and offered_cover_letter_or_apply) or is_cover_letter_intent:
        working_history.append({
            "role": "user",
            "content": (
                "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user responded affirmatively to your offer to draft a cover letter and queue the job for application. "
                "CRITICAL INSTRUCTIONS: "
                "1. DO NOT call 'search_naukri_jobs' or 'search_web_jobs'. DO NOT perform a new job search! "
                "2. Look at the specific target job and company from the previous turn in the conversation (e.g. Tekskills India Pvt Ltd - Backend Python Developer). "
                "3. Draft a tailored, high-impact 3-paragraph Cover Letter and a 3-sentence LinkedIn Recruiter Outreach note in clean Markdown for that specific employer. "
                "4. Call 'queue_job_for_apply' with the target job details to queue it into the user's application tracker, and confirm to the user that the job has been queued with their resume and cover letter ready."
            )
        })
    elif is_job_search_intent and not user_wants_resume:
        working_history.append({
            "role": "user",
            "content": "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user requested a direct job search without asking for resume scoring. DO NOT call 'read_my_resume' or 'score_and_rank_jobs'. Simply present the job results sorted by recency."
        })
    elif not is_job_search_intent and not user_wants_resume and not is_affirmative:
        working_history.append({
            "role": "user",
            "content": "[SYSTEM INSTRUCTION FOR CURRENT TURN]: The user is asking a conversational, technical, or follow-up question. DO NOT execute job search tools ('search_naukri_jobs', 'search_web_jobs') unless explicitly requested. Answer the user's specific query directly and thoroughly."
        })

    inferred_days = None
    m_days = re.search(r'(?:last|past|within)\s*(\d+)\s*days?', last_user_raw_msg, re.IGNORECASE)
    if m_days:
        try:
            inferred_days = int(m_days.group(1))
        except Exception:
            pass
    elif any(term in last_user_raw_msg.lower() for term in ["recent", "latest", "today", "fresh"]):
        inferred_days = 7
    if "naukri" in last_user_raw_msg.lower() and not load_naukri_cookies():
        yield {
            "type": "auth_required",
            "data": {
                "platform": "naukri",
                "message": "Naukri authentication required. Please connect your Naukri account to search jobs.",
                "query": last_user_raw_msg
            }
        }
        auth_msg = "⚠️ **Naukri Authentication Required**\n\nTo search live jobs on Naukri, please log in using the connection window that just opened."

        for word in auth_msg.split(" "):
            yield {"type": "token", "data": word + " "}
            await asyncio.sleep(0.015)
        yield {"type": "done", "data": {"content": auth_msg, "job_cards": []}}
        return

    nvidia_k = nvidia_key or settings.NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
    claude_key = anthropic_key or settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
    google_key = gemini_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    collected_jobs = []
    max_turns = 6
    accumulated_content = ""

    # Determine provider execution mode (NVIDIA NIM is primary for Job Find Agent)
    if (model == "auto" or "nvidia" in model) and nvidia_k:
        active_tier = "nvidia"
    elif (model == "auto" or "claude" in model) and claude_key:
        active_tier = "claude"
    elif (model == "auto" or "gemini" in model) and google_key:
        active_tier = "gemini"
    else:
        active_tier = "ollama"
        if "nvidia" in model and not nvidia_k:
            yield {"type": "status", "data": "⚠️ NVIDIA key missing. Using Local Ollama..."}
        elif "gemini" in model and not google_key:
            yield {"type": "status", "data": "⚠️ Gemini key missing. Using Local Ollama..."}
        elif "claude" in model and not claude_key:
            yield {"type": "status", "data": "⚠️ Claude key missing. Using Local Ollama..."}

    tier_labels = {
        "nvidia": "NVIDIA Nemotron 120B (AI Scout)",
        "claude": "Claude 3.5 Haiku",
        "gemini": "Google Gemini 1.5 Flash",
        "ollama": "Local Ollama"
    }
    yield {"type": "status", "data": f"⚡ Connected to {tier_labels.get(active_tier, active_tier.capitalize())}..."}

    # Safe fallback local model (only valid local models)
    target_local = "llama3.2:3b" if "llama" in model else "qwen2.5"

    for turn in range(max_turns):
        trimmed = manage_context(working_history)
        turn_result = None

        # ── TIER 0: NVIDIA NIM (NVIDIA Nemotron 3.5 120B Super) ──
        if active_tier == "nvidia":
            try:
                yield {"type": "status", "data": "🟢 NVIDIA Nemotron 120B is reasoning..."}
                turn_result = await run_nvidia_turn(
                    trimmed,
                    system_prompt,
                    api_key=nvidia_k,
                    base_url=settings.NVIDIA_BASE_URL,
                    model=settings.NVIDIA_MODEL
                )
                if turn_result.get("reasoning"):
                    first_line = turn_result["reasoning"].strip().split("\n")[0][:75]
                    yield {"type": "status", "data": f"🧠 Reasoning: {first_line}..."}
            except Exception as e:
                print(f"[NVIDIA ERROR] {repr(e)}", flush=True)
                yield {"type": "status", "data": f"⚡ NVIDIA NIM unavailable ({str(e)[:30]}). Cascading..."}
                if claude_key:
                    active_tier = "claude"
                elif google_key:
                    active_tier = "gemini"
                else:
                    active_tier = "ollama"

        # ── TIER 1: CLAUDE ──
        if active_tier == "claude" and not turn_result:
            try:
                yield {"type": "status", "data": "⚡ Claude 3.5 is analyzing..."}
                turn_result = await run_claude_turn(trimmed, system_prompt, claude_key)
            except Exception as e:
                yield {"type": "status", "data": f"⚡ Claude limit reached ({str(e)[:30]}). Cascading to Gemini..."}
                active_tier = "gemini" if google_key else "ollama"

        # ── TIER 2: GEMINI ──
        if active_tier == "gemini" and not turn_result:
            try:
                yield {"type": "status", "data": "💎 Gemini 1.5 Flash is analyzing..."}
                turn_result = await run_gemini_turn(trimmed, system_prompt, google_key)
            except Exception as e:
                print(f"[GEMINI ERROR] {repr(e)}", flush=True)
                yield {"type": "status", "data": f"💎 Gemini limit reached ({str(e)[:30]}). Cascading to Local Ollama..."}
                active_tier = "ollama"

        # ── TIER 3: LOCAL OLLAMA (BEDROCK GUARANTEE) ──
        if active_tier == "ollama" and not turn_result:
            try:
                yield {"type": "status", "data": f"🏠 Running Local Ollama ({target_local})..."}
                turn_result = await run_ollama_turn(trimmed, model=target_local)
            except Exception as e:
                err = f"All models failed. Local Ollama error: {type(e).__name__}: {str(e) or 'Inference timed out'}"
                yield {"type": "token", "data": err}
                yield {"type": "done", "data": {"content": err, "job_cards": []}}
                return

        content = turn_result.get("content", "")
        tool_calls = turn_result.get("tool_calls", [])

        asst_msg: Dict[str, Any] = {"role": "assistant", "content": content or None}
        if tool_calls:
            asst_msg["tool_calls"] = tool_calls
        working_history.append(asst_msg)

        if content:
            accumulated_content += content
            yield {"type": "token", "data": content}

        if not tool_calls:
            break

        # Process Tools - strictly sort so read_my_resume and search_naukri_jobs execute FIRST
        def tool_sort_key(t):
            fn_name = t.get("function", {}).get("name", "")
            if fn_name == "read_my_resume":
                return -1
            if fn_name == "search_naukri_jobs":
                return 0
            if fn_name == "search_web_jobs":
                return 1
            if fn_name == "score_and_rank_jobs":
                return 2
            return 3

        tool_calls.sort(key=tool_sort_key)

        for tool in tool_calls:
            func = tool.get("function", {})
            func_name = func.get("name", "")
            func_args = func.get("arguments", {})
            if isinstance(func_args, str):
                try:
                    func_args = json.loads(func_args)
                except Exception:
                    func_args = {}

            active_days = func_args.get("days") or inferred_days
            days_suffix = f" (last {active_days} days)" if active_days else ""
            status_labels = {
                "read_my_resume": "📄 Reading your resume...",
                "search_naukri_jobs": f"🔍 Scraping Naukri first for '{func_args.get('role', 'jobs')}' in {func_args.get('location', 'India')}{days_suffix}...",
                "search_web_jobs": f"🔍 Searching LinkedIn & Indeed to supplement opportunities{days_suffix}...",
                "score_and_rank_jobs": "🧠 Scoring jobs against your resume...",
                "queue_job_for_apply": "📨 Preparing application queue...",
                "get_applied_jobs": "📋 Fetching applied jobs and proof screenshots from application tracker...",
                "get_saved_jobs": "🔖 Fetching saved jobs from your tracker...",
                "get_interview_jobs": "📅 Fetching interview schedules from your tracker...",
            }
            yield {"type": "status", "data": status_labels.get(func_name, f"⚙️ Running {func_name}...")}

            if func_name == "search_naukri_jobs" and not load_naukri_cookies():
                yield {
                    "type": "auth_required",
                    "data": {
                        "platform": "naukri",
                        "message": "Naukri account session is required to search live listings.",
                        "query": last_user_raw_msg
                    }
                }
            result = await execute_tool(
                func_name,
                func_args,
                collected_jobs,
                model=target_local,
                user_inferred_days=inferred_days,
                user_wants_resume=user_wants_resume,
                is_job_search_intent=is_job_search_intent,
                google_key=google_key,
                claude_key=claude_key
            )

            call_id = tool.get("id") or f"call_{func_name}_{turn}"
            working_history.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": func_name,
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            })

            if collected_jobs:
                for j in collected_jobs:
                    j["platform"] = svc_normalize_platform(j)

                if not user_wants_resume:
                    for j in collected_jobs:
                        j["score"] = 0
                        j["match_reasons"] = []
                        j["missing_skills"] = []

                from backend.app.services.naukri_service import parse_job_age_days
                def job_recency_key(j):
                    age = parse_job_age_days(j.get("posted_date"))
                    plat = (j.get("platform") or "").lower()
                    plat_p = 0 if plat == "naukri" else 1 if plat == "linkedin" else 2
                    return (age, plat_p)
                collected_jobs.sort(key=job_recency_key)
                yield {"type": "job_cards", "data": collected_jobs}

    if not accumulated_content.strip():
        if collected_jobs:
            if user_wants_resume:
                accumulated_content = f"Here are the top opportunities evaluated against your resume, sorted by recency:"
            else:
                accumulated_content = f"Here are the latest job postings found across platforms, sorted from most recent:"
            yield {"type": "token", "data": accumulated_content}
        else:
            accumulated_content = "How can I assist you with your tasks or questions today?"
            yield {"type": "token", "data": accumulated_content}

    for j in collected_jobs:
        j["platform"] = svc_normalize_platform(j)

    yield {"type": "done", "data": {"content": accumulated_content, "job_cards": collected_jobs}}
