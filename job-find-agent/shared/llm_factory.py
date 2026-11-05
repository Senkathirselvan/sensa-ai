"""
Universal LLM Factory across all agents.
Supports:
  - NVIDIA NIM (Free API on H100s via OpenAI format)
  - Google Gemini (AI Studio Free Tier)
  - Local Ollama (100% Free & Offline)
  - OpenAI / Anthropic (Paid if keys provided)
"""
import os
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel


def get_agent_llm(model_override: Optional[str] = None, temperature: float = 0.2) -> BaseChatModel:
    """
    Returns a LangChain/LangGraph-compatible ChatModel.
    Format: '<provider>/<model_name>'
    Examples:
      - 'nvidia/meta/llama-3.3-70b-instruct'
      - 'nvidia/meta/llama-3.1-8b-instruct'
      - 'gemini/gemini-2.5-flash'
      - 'ollama/qwen2.5:7b'
      - 'openai/gpt-4o'
    """
    model_str = (
        model_override
        or os.getenv("AGENT_MODEL")
        or os.getenv("SCOUT_LLM")
        or os.getenv("DEFAULT_LLM", "ollama/qwen2.5:7b")
    )

    if "/" not in model_str:
        # Default to ollama if only model name is provided
        provider = "ollama"
        model_name = model_str
    else:
        provider, model_name = model_str.split("/", 1)

    provider = provider.lower()

    # 1. NVIDIA NIM (Free API)
    if provider == "nvidia":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            # Fallback to local Ollama if key missing
            print("⚠️ NVIDIA_API_KEY missing, falling back to local Ollama...")
            return get_agent_llm("ollama/qwen2.5:7b", temperature)
        return ChatOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            model=model_name,
            temperature=temperature
        )

    # 2. Google Gemini (Free Tier)
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("⚠️ GEMINI_API_KEY missing, falling back to local Ollama...")
            return get_agent_llm("ollama/qwen2.5:7b", temperature)
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            model=model_name,
            temperature=temperature
        )

    # 3. Local Ollama (Free & Offline)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # In Docker containers, host is accessible via host.docker.internal
        if os.getenv("IN_DOCKER"):
            base_url = os.getenv("OLLAMA_DOCKER_URL", "http://host.docker.internal:11434")
        return ChatOllama(
            base_url=base_url,
            model=model_name,
            temperature=temperature
        )

    # 4. OpenAI (Optional Paid)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        return ChatOpenAI(
            api_key=api_key,
            model=model_name,
            temperature=temperature
        )

    raise ValueError(f"Unsupported LLM provider: '{provider}'")
