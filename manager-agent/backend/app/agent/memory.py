from typing import Dict, List, Optional
from collections import defaultdict

class SessionMemoryManager:
    """
    In-memory session history manager with configurable window size.
    """
    def __init__(self, max_history: int = 12):
        self.max_history = max_history
        self._sessions: Dict[str, List[Dict[str, str]]] = defaultdict(list)

    def add_message(self, session_id: str, role: str, content: str):
        if not session_id or not content:
            return
        self._sessions[session_id].append({"role": role, "content": content})
        if len(self._sessions[session_id]) > self.max_history:
            self._sessions[session_id] = self._sessions[session_id][-self.max_history:]

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        return list(self._sessions.get(session_id, []))

    def clear(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

memory_manager = SessionMemoryManager()

