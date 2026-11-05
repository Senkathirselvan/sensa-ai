import asyncio
from typing import Dict, Any, Optional

class ApplicationMemory:
    """Stores in-flight application sessions and Human-in-the-Loop pause events."""

    _active_events: Dict[str, asyncio.Event] = {}
    _abort_flags: Dict[str, bool] = {}
    _session_data: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_session(cls, session_id: str, data: Dict[str, Any]):
        cls._active_events[session_id] = asyncio.Event()
        cls._abort_flags[session_id] = False
        cls._session_data[session_id] = data

    @classmethod
    def get_event(cls, session_id: str) -> Optional[asyncio.Event]:
        return cls._active_events.get(session_id)

    @classmethod
    def confirm_session(cls, session_id: str) -> bool:
        """Sets the event flag to authorize final submission."""
        event = cls._active_events.get(session_id)
        if event:
            event.set()
            return True
        return False

    @classmethod
    def abort_session(cls, session_id: str) -> bool:
        cls._abort_flags[session_id] = True
        event = cls._active_events.get(session_id)
        if event:
            event.set()  # Unblock to allow clean exit
        return True

    @classmethod
    def is_aborted(cls, session_id: str) -> bool:
        return cls._abort_flags.get(session_id, False)

    @classmethod
    def cleanup(cls, session_id: str):
        cls._active_events.pop(session_id, None)
        cls._abort_flags.pop(session_id, None)
        cls._session_data.pop(session_id, None)

