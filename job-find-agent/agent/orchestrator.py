import os
import json
import inspect
import ollama
from typing import List, Dict, Callable, Optional
from tools import TOOL_DEFINITIONS, TOOL_MAP
from agent.prompt import SYSTEM_PROMPT
from agent.memory import manage_context

MODEL_NAME = "qwen2.5"


def run_agent_loop(
    chat_history: List[Dict],
    tool_callback: Optional[Callable[[str, dict], None]] = None,
    model_name: Optional[str] = None
) -> str:
    """Runs the ReAct loop: calls local Ollama model, invokes tools, feeds results back."""
    target_model = model_name or MODEL_NAME

    # Dynamically inject resume status so the LLM knows resume.pdf is on disk
    resume_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "resume.pdf")
    resume_exists = os.path.exists(resume_path)
    resume_note = (
        f"\n\nCURRENT STATUS: The user's resume is ACTIVE and uploaded on disk at 'data/resume.pdf' ({os.path.getsize(resume_path)/1024:.1f} KB). DO NOT ask them to upload it. Call 'read_my_resume' immediately if they mention resume, background, or job matches."
        if resume_exists
        else "\n\nCURRENT STATUS: No resume found at 'data/resume.pdf'. Instruct the user to upload their resume via the + attachment button."
    )
    active_prompt = SYSTEM_PROMPT.strip() + resume_note

    if chat_history and chat_history[0].get("role") == "system":
        chat_history[0]["content"] = active_prompt
    else:
        chat_history.insert(0, {"role": "system", "content": active_prompt})

    # Fast-path for simple conversational greetings (avoids heavy tool-schema overhead)
    last_user_msg = next((m.get("content", "").strip().lower() for m in reversed(chat_history) if m.get("role") == "user"), "")
    is_greeting = last_user_msg in [
        "hi", "hello", "hey", "hola", "hi there", "hello there", 
        "good morning", "good evening", "good afternoon", "greetings", "help"
    ]
    if is_greeting:
        try:
            response = ollama.chat(
                model=target_model,
                messages=manage_context(chat_history),
                keep_alive="30m",
                options={"num_predict": 128}
            )
            reply = response.message.content or "Hello! How can I assist you in your job search today?"
            chat_history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"Ollama Connection Error: {str(e)}. Make sure Ollama is running (`ollama serve`)."

    max_turns = 8
    for _ in range(max_turns):
        trimmed_history = manage_context(chat_history)

        try:
            response = ollama.chat(
                model=target_model,
                messages=trimmed_history,
                tools=TOOL_DEFINITIONS,
                keep_alive="30m"
            )
        except Exception as e:
            return f"Ollama Connection Error: {str(e)}. Make sure Ollama is running (`ollama serve`)."

        message = response.message
        msg_dict = {
            "role": getattr(message, "role", "assistant"),
            "content": getattr(message, "content", "") or ""
        }
        if getattr(message, "tool_calls", None):
            msg_dict["tool_calls"] = message.tool_calls
        chat_history.append(msg_dict)

        if not getattr(message, "tool_calls", None):
            return msg_dict["content"] or "Completed task."

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = tool_call.function.arguments

            if tool_callback:
                tool_callback(func_name, func_args)

            fn = TOOL_MAP.get(func_name)
            if fn:
                try:
                    sig = inspect.signature(fn)
                    valid_params = set(sig.parameters.keys())
                    filtered_args = {k: v for k, v in func_args.items() if k in valid_params} if isinstance(func_args, dict) else {}
                    result = fn(**filtered_args)
                except Exception as e:
                    result = f"Error executing {func_name}: {str(e)}"
            else:
                result = f"Unknown tool: {func_name}"

            chat_history.append({
                "role": "tool",
                "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            })

    return "Reached maximum reasoning steps. Please refine your query."
