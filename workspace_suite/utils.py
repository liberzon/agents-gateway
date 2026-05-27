from datetime import datetime
from typing import Any, Dict

import httpx


def timeout_obj(t: float | tuple[float, float]) -> httpx.Timeout:
    if isinstance(t, tuple):
        return httpx.Timeout(connect=t[0], read=t[1])
    return httpx.Timeout(timeout=t)


def json_or_text(resp: httpx.Response) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text[:400]}


def parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    s = value.strip()
    if s.endswith("Z"):
        s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def strip_tz(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt
