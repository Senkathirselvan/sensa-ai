import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional
import httpx

logger = logging.getLogger("manager_agent.clients")

class BaseWorkerClient:
    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=10.0, read=timeout)

    async def get_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"GET {url} failed with status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.error(f"GET {url} connection error: {e}")
        return None

    async def post_json(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    return res.json()
                logger.warning(f"POST {url} failed with status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.error(f"POST {url} connection error: {e}")
        return None

    async def stream_sse(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams Server-Sent Events from downstream worker, decoding `data:` lines into JSON.
        """
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0, read=180.0)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield {"type": "error", "data": f"Worker returned HTTP {response.status_code}"}
                        return

                    current_event_type = "message"
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            current_event_type = "message"
                            continue
                        if line.startswith("event:"):
                            current_event_type = line[6:].strip()
                            continue
                        if line.startswith("data:"):
                            raw_data = line[5:].strip()
                            try:
                                parsed = json.loads(raw_data)
                            except Exception:
                                parsed = raw_data

                            if current_event_type != "message":
                                yield {"type": current_event_type, "data": parsed}
                            elif isinstance(parsed, dict) and "type" in parsed:
                                yield parsed
                            elif isinstance(parsed, list):
                                yield {"type": "job_cards", "data": parsed}
                            elif isinstance(parsed, str):
                                if any(parsed.startswith(p) for p in ["⚡", "🟢", "🧠", "🔖", "🔍", "📋", "📨", "📄", "🛡️"]):
                                    yield {"type": "status", "data": parsed}
                                else:
                                    yield {"type": "token", "data": parsed}
                            else:
                                yield {"type": "token", "data": str(parsed)}
        except Exception as e:
            logger.error(f"SSE streaming error from {url}: {e}")
            yield {"type": "error", "data": f"Communication failed with worker ({url}): {e}"}
