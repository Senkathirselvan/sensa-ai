from typing import List, Dict

def manage_context(messages: List[Dict], max_messages: int = 12) -> List[Dict]:
    """Ensures conversation history doesn't exceed LLM context window while preserving the system prompt."""
    if not messages:
        return []
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    trimmed = non_system[-max_messages:]
    return system_msgs + trimmed

