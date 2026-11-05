import re
import json
import logging
from typing import Dict, Any, Optional
import httpx
from backend.app.config import settings
from backend.app.api.schemas import TargetAgent, ManagerRoutingDecision, WorkflowStep
from backend.app.agent.prompts import MANAGER_ROUTER_SYSTEM_PROMPT

logger = logging.getLogger("manager_agent.router")

def fast_pattern_classifier(user_msg: str) -> Optional[ManagerRoutingDecision]:
    """
    Ultra-low-latency deterministic heuristic classifier (<1ms).
    Handles unambiguous standard commands and user intents instantly.
    """
    clean = user_msg.strip().lower()

    # 1. Multi-step compound intents
    has_find = any(k in clean for k in ["find", "search", "looking for"])
    has_tailor = any(k in clean for k in ["tailor", "prep resume", "build resume", "custom resume"])
    has_apply = any(k in clean for k in ["apply", "submit application", "auto apply"])

    if (has_find and (has_tailor or has_apply)) or (has_tailor and has_apply):
        steps = []
        step_idx = 1
        if has_find:
            steps.append(WorkflowStep(
                step_number=step_idx,
                target_agent=TargetAgent.JOB_FIND,
                action="search_jobs",
                input_payload={"query": user_msg}
            ))
            step_idx += 1
        if has_tailor:
            steps.append(WorkflowStep(
                step_number=step_idx,
                target_agent=TargetAgent.RESUME_PREP,
                action="tailor_resume",
                input_payload={"instruction": user_msg}
            ))
            step_idx += 1
        if has_apply:
            steps.append(WorkflowStep(
                step_number=step_idx,
                target_agent=TargetAgent.JOB_APPLY,
                action="submit_application",
                input_payload={"instruction": user_msg}
            ))

        return ManagerRoutingDecision(
            target_agent=TargetAgent.MULTI_STEP,
            confidence=0.98,
            intent_summary="Compound multi-agent workflow request",
            extracted_params={"instruction": user_msg},
            pipeline_steps=steps,
            requires_human_confirmation=has_apply
        )

    # 2. Saved / Applied / Interview Tracker Intents -> Job Find Agent
    if any(k in clean for k in [
        "saved job", "saved jobs", "show my saved", "show saved",
        "applied job", "applied jobs", "show my applied", "show applied", "my applications",
        "interview job", "interview scheduled", "my interview", "show my interview"
    ]):
        return ManagerRoutingDecision(
            target_agent=TargetAgent.JOB_FIND,
            confidence=0.99,
            intent_summary="Job tracker inquiry (saved, applied, or interview status)",
            extracted_params={"query": user_msg}
        )

    # 3. Direct Job Searches -> Job Find Agent
    if any(clean.startswith(p) for p in ["find ", "search ", "looking for ", "show jobs", "openings in "]) or \
       any(k in clean for k in ["naukri", "linkedin jobs", "indeed jobs", "vacancies"]):
        return ManagerRoutingDecision(
            target_agent=TargetAgent.JOB_FIND,
            confidence=0.95,
            intent_summary="Job search and portal discovery request",
            extracted_params={"query": user_msg}
        )

    # 4. Resume Editing / Styling / Preparing / Generating -> Resume Prep Agent
    resume_keywords = ["resume", "cv"]
    resume_actions = [
        "prepare", "create", "make", "build", "generate", "write", "tailor",
        "edit", "update", "format", "style", "refine", "draft", "new resume"
    ]
    is_resume_intent = (
        any(k in clean for k in [
            "theme color", "color swatch", "change color", "change font", "tighten page",
            "margin", "recompile", "download pdf", "resume preview", "ats score", "audit",
            "ats check", "score my resume", "evaluate my resume", "check my resume",
            "xyz audit", "ats compliance", "surgically", "surgical", "only change",
            "only update", "precision edit", "change my title", "update my title",
            "change bullet", "update bullet", "modify bullet", "1 page", "one page",
            "2 page", "single page", "paginate", "fit to page"
        ])
        or (any(rk in clean for rk in resume_keywords) and any(ra in clean for ra in resume_actions))
        or clean.endswith("new resume")
        or clean.endswith("a resume")
    )

    if is_resume_intent:
        extracted_role = "Python Developer" if "python" in clean else "Software Engineer"
        return ManagerRoutingDecision(
            target_agent=TargetAgent.RESUME_PREP,
            confidence=0.98,
            intent_summary="Resume preparation, tailoring, or styling request",
            extracted_params={"role": extracted_role, "instruction": user_msg}
        )

    # 5. Direct Browser Apply -> Job Apply Agent
    if ("http://" in clean or "https://" in clean) and any(k in clean for k in ["apply", "submit", "easy apply"]):
        url_match = re.search(r'https?://[^\s]+', user_msg)
        return ManagerRoutingDecision(
            target_agent=TargetAgent.JOB_APPLY,
            confidence=0.99,
            intent_summary="Direct portal URL application submission",
            extracted_params={"job_url": url_match.group(0) if url_match else "", "query": user_msg},
            requires_human_confirmation=True
        )

    return None

async def classify_intent_llm(user_msg: str) -> ManagerRoutingDecision:
    """
    Calls NVIDIA Nemotron 120B Super / OpenAI API for structured intent classification.
    """
    if not settings.NVIDIA_API_KEY:
        # Fallback to general chat if no API key
        return ManagerRoutingDecision(
            target_agent=TargetAgent.GENERAL_CHAT,
            confidence=0.7,
            intent_summary="General conversational request (offline fallback)",
            extracted_params={"query": user_msg}
        )

    url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.NVIDIA_ROUTER_MODEL,
        "messages": [
            {"role": "system", "content": MANAGER_ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this request:\n\n{user_msg}"}
        ],
        "temperature": 0.1,
        "max_tokens": 512,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
                parsed = json.loads(raw_content)

                target_str = parsed.get("target_agent", "general-chat")
                try:
                    target_enum = TargetAgent(target_str)
                except ValueError:
                    target_enum = TargetAgent.GENERAL_CHAT

                return ManagerRoutingDecision(
                    target_agent=target_enum,
                    confidence=float(parsed.get("confidence", 0.9)),
                    intent_summary=parsed.get("intent_summary", "Classified via Manager LLM"),
                    extracted_params=parsed.get("extracted_params", {}),
                    pipeline_steps=[WorkflowStep(**s) for s in parsed.get("pipeline_steps", [])] if parsed.get("pipeline_steps") else None,
                    requires_human_confirmation=bool(parsed.get("requires_human_confirmation", False))
                )
    except Exception as e:
        logger.warning(f"[classify_intent_llm] LLM classification fallback due to: {e}")

    # Fallback to general chat
    return ManagerRoutingDecision(
        target_agent=TargetAgent.GENERAL_CHAT,
        confidence=0.7,
        intent_summary="General conversation / technical inquiry",
        extracted_params={"query": user_msg}
    )

async def route_user_request(user_msg: str) -> ManagerRoutingDecision:
    """
    Main router entrypoint:
    1. Runs sub-millisecond fast-pattern heuristics first.
    2. Falls back to Nemotron 120B reasoning classifier if ambiguous.
    """
    fast_decision = fast_pattern_classifier(user_msg)
    if fast_decision:
        return fast_decision

    return await classify_intent_llm(user_msg)

