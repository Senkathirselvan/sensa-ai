from typing import List, Dict

MAX_MESSAGES = 14


def manage_context(history: List[Dict]) -> List[Dict]:
    """Keeps the system prompt and trims the oldest turns when history grows too large."""
    if len(history) <= MAX_MESSAGES:
        return history

    system_msg = history[0] if history and history[0].get("role") == "system" else None
    recent_turns = history[-(MAX_MESSAGES - 1):]

    if system_msg and recent_turns[0].get("role") != "system":
        return [system_msg] + recent_turns
    return recent_turns
