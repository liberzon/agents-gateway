import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import Attendee, EventCreateRequest, EventResult
from ..utils import json_or_text, parse_dt, timeout_obj

logger = logging.getLogger(__name__)


class GoogleCalendarProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://www.googleapis.com/calendar/v3"

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
            "summary": req.summary,
            "description": req.description,
            "start": {"dateTime": req.start.isoformat(), "timeZone": tz},
            "end": {"dateTime": req.end.isoformat(), "timeZone": tz},
        }
        if req.attendees:
            payload["attendees"] = [{"displayName": a.name or a.email, "email": a.email} for a in req.attendees]
        if req.location:
            payload["location"] = req.location
        if req.conference:
            payload["conferenceData"] = {
                "createRequest": {
                    "requestId": f"req-{int(req.start.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/calendars/{calendar_id}/events?sendUpdates={req.send_updates}&conferenceDataVersion=1"

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
            return EventResult(
                status="success",
                event_id=data.get("id"),
                html_link=data.get("htmlLink"),
                conference_link=data.get("hangoutLink")
                or (data.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri")),
                summary=req.summary,
                start=req.start,
                end=req.end,
                timezone=tz,
                attendees=req.attendees,
                location=req.location,
            )
        except Exception as e:
            logger.exception("Google create_event failed")
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
        url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
        try:
            client = self._client(http_timeout)
            resp = client.patch(url, headers=headers, json=patch)
            if resp.status_code >= 400:
                return EventResult(status="error", error=json_or_text(resp))
            data = resp.json()
            return EventResult(status="success", event_id=data.get("id"), html_link=data.get("htmlLink"))
        except Exception as e:
            logger.exception("Google update_event failed")
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
        url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}?sendUpdates={send_updates}"
        try:
            client = self._client(http_timeout)
            resp = client.delete(url, headers=headers)
            if resp.status_code not in (200, 204):
                return EventResult(status="error", error=json_or_text(resp))
            return EventResult(status="success", event_id=event_id)
        except Exception as e:
            logger.exception("Google cancel_event failed")
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
        params: Dict[str, Any] = {"maxResults": max_results, "singleEvents": True, "orderBy": "startTime"}
        if time_min:
            params["timeMin"] = time_min.isoformat()
        if time_max:
            params["timeMax"] = time_max.isoformat()
        if q:
            params["q"] = q

        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}/calendars/{calendar_id}/events"
        try:
            client = self._client(http_timeout)
            resp = client.get(url, headers=headers, params=params)  # type: ignore[arg-type]
            if resp.status_code >= 400:
                return [EventResult(status="error", error=json_or_text(resp))]
            data = resp.json()
            items = data.get("items", [])
            results: List[EventResult] = []
            for it in items:
                start_iso = (it.get("start", {}) or {}).get("dateTime") or (it.get("start", {}) or {}).get("date")
                end_iso = (it.get("end", {}) or {}).get("dateTime") or (it.get("end", {}) or {}).get("date")
                start_dt = parse_dt(start_iso) if start_iso else None
                end_dt = parse_dt(end_iso) if end_iso else None
                results.append(
                    EventResult(
                        status="success",
                        event_id=it.get("id"),
                        html_link=it.get("htmlLink"),
                        summary=it.get("summary"),
                        start=start_dt,
                        end=end_dt,
                        timezone=(it.get("start", {}) or {}).get("timeZone"),
                        attendees=tuple(
                            Attendee(name=a.get("displayName"), email=a.get("email"))
                            for a in it.get("attendees", []) or []
                        ),
                        location=it.get("location"),
                    )
                )
            return results
        except Exception as e:
            logger.exception("Google list_events failed")
            return [EventResult(status="error", error={"message": str(e)})]
