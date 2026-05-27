from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ..models import EventCreateRequest, EventResult


class CalendarProvider(Protocol):
    def create_event(
        self,
        token: str,
        calendar_id: str,
        req: EventCreateRequest,
        http_timeout: float | Tuple[float, float] = 15.0,
        default_timezone: str = "UTC",
    ) -> EventResult: ...
    def update_event(
        self,
        token: str,
        calendar_id: str,
        event_id: str,
        patch: Dict[str, Any],
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EventResult: ...
    def cancel_event(
        self,
        token: str,
        calendar_id: str,
        event_id: str,
        send_updates: str = "all",
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EventResult: ...
    def list_events(
        self,
        token: str,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        q: Optional[str] = None,
        max_results: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> List[EventResult]: ...
