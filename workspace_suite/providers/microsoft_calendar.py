import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import Attendee, EventCreateRequest, EventResult
from ..utils import json_or_text, parse_dt, strip_tz, timeout_obj

logger = logging.getLogger(__name__)


class MicrosoftCalendarProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://graph.microsoft.com/v1.0"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def create_event(
        self,
        token: str,
        calendar_id: str,
        req: EventCreateRequest,
        http_timeout: float | Tuple[float, float] = 15.0,
        default_timezone: str = "UTC",
    ) -> EventResult:
        tz = req.timezone or default_timezone
        payload: Dict[str, Any] = {
            "subject": req.summary,
            "body": {"contentType": "HTML", "content": req.description or ""},
            "start": {"dateTime": strip_tz(req.start).isoformat(), "timeZone": tz},
            "end": {"dateTime": strip_tz(req.end).isoformat(), "timeZone": tz},
            "attendees": [
                {
                    "emailAddress": {"address": a.email, "name": a.name or a.email},
                    "type": "required" if a.role == "required" else "optional",
                }
                for a in req.attendees
            ],
        }
        if req.location:
            payload["location"] = {"displayName": req.location}
        if req.conference:
            payload["isOnlineMeeting"] = True
            payload["onlineMeetingProvider"] = "teamsForBusiness"

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = (
            f"{self.base_url}/me/events"
            if calendar_id == "primary"
            else f"{self.base_url}/me/calendars/{calendar_id}/events"
        )

        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return EventResult(
                    status="error",
                    error=json_or_text(resp),
                    summary=req.summary,
                    start=req.start,
                    end=req.end,
                    timezone=tz,
                    attendees=req.attendees,
                    location=req.location,
                )
            data = resp.json()
            join_url = (data.get("onlineMeeting") or {}).get("joinUrl") if req.conference else None
            return EventResult(
                status="success",
                event_id=data.get("id"),
                html_link=data.get("webLink"),
                conference_link=join_url,
                summary=req.summary,
                start=req.start,
                end=req.end,
                timezone=tz,
                attendees=req.attendees,
                location=req.location,
            )
        except Exception as e:
            logger.exception("Microsoft create_event failed")
            return EventResult(status="error", error={"message": str(e)})

    def update_event(
        self,
        token: str,
        calendar_id: str,
        event_id: str,
        patch: Dict[str, Any],
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EventResult:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = (
            f"{self.base_url}/me/events/{event_id}"
            if calendar_id == "primary"
            else f"{self.base_url}/me/calendars/{calendar_id}/events/{event_id}"
        )
        try:
            client = self._client(http_timeout)
            resp = client.patch(url, headers=headers, json=patch)
            if resp.status_code >= 400:
                return EventResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EventResult(status="success", event_id=data.get("id"), html_link=data.get("webLink"))
        except Exception as e:
            logger.exception("Microsoft update_event failed")
            return EventResult(status="error", error={"message": str(e)})

    def cancel_event(
        self,
        token: str,
        calendar_id: str,
        event_id: str,
        send_updates: str = "all",
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> EventResult:
        headers = {"Authorization": f"Bearer {token}"}
        url = (
            f"{self.base_url}/me/events/{event_id}"
            if calendar_id == "primary"
            else f"{self.base_url}/me/calendars/{calendar_id}/events/{event_id}"
        )
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (204,):
                return EventResult(status="error", error=json_or_text(resp))
            return EventResult(status="success", event_id=event_id)
        except Exception as e:
            logger.exception("Microsoft cancel_event failed")
            return EventResult(status="error", error={"message": str(e)})

    def list_events(
        self,
        token: str,
        calendar_id: str,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        q: Optional[str] = None,
        max_results: int = 100,
        http_timeout: float | Tuple[float, float] = 15.0,
    ) -> List[EventResult]:
        params: Dict[str, Any] = {"$top": max_results, "$orderby": "start/dateTime"}
        if q:
            params["$search"] = f'"{q}"'
        path = "me/calendarView" if calendar_id == "primary" else f"me/calendars/{calendar_id}/calendarView"
        if time_min and time_max:
            params["startDateTime"] = strip_tz(time_min).isoformat()
            params["endDateTime"] = strip_tz(time_max).isoformat()
        url = f"{self.base_url}/{path}"

        headers = {"Authorization": f"Bearer {token}"}
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [EventResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            items = data.get("value", [])
            results: List[EventResult] = []
            for it in items:
                start_block = it.get("start") or {}
                end_block = it.get("end") or {}
                start_iso = start_block.get("dateTime")
                end_iso = end_block.get("dateTime")
                start_dt = parse_dt(start_iso) if start_iso else None
                end_dt = parse_dt(end_iso) if end_iso else None
                results.append(
                    EventResult(
                        status="success",
                        event_id=it.get("id"),
                        html_link=it.get("webLink"),
                        summary=it.get("subject"),
                        start=start_dt,
                        end=end_dt,
                        timezone=start_block.get("timeZone"),
                        attendees=tuple(
                            Attendee(
                                name=a.get("emailAddress", {}).get("name"),
                                email=a.get("emailAddress", {}).get("address"),
                            )
                            for a in it.get("attendees", []) or []
                        ),
                        location=(it.get("location") or {}).get("displayName"),
                    )
                )
            return results
        except Exception as e:
            logger.exception("Microsoft list_events failed")
            return [EventResult(status="error", error={"message": str(e)})]
