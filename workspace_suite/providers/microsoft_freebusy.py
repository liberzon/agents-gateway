import logging
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import BusySlot, FreeBusyCalendar, FreeBusyRequest, FreeBusyResult
from ..utils import json_or_text, timeout_obj

logger = logging.getLogger(__name__)


class MicrosoftFreeBusyProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://graph.microsoft.com/v1.0"

    def _client(self, http_timeout: float | Tuple[float, float]) -> httpx.Client:
        if self.http:
            return self.http
        return httpx.Client(timeout=timeout_obj(http_timeout or self.config.http_timeout))

    def query_freebusy(
        self,
        token: str,
        req: FreeBusyRequest,
        http_timeout: float | Tuple[float, float] = 15.0,
        default_timezone: str = "UTC",
    ) -> FreeBusyResult:
        tz = req.timezone or default_timezone
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = f"{self.base_url}/me/calendar/getSchedule"
        payload = {
            "schedules": list(req.calendars),
            "startTime": {"dateTime": req.time_min.isoformat(), "timeZone": tz},
            "endTime": {"dateTime": req.time_max.isoformat(), "timeZone": tz},
            "availabilityViewInterval": req.interval_minutes,
        }
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return FreeBusyResult(status="error", error=json_or_text(resp))
            data = resp.json()
            calendars = []
            for entry in data.get("value", []):
                name = entry.get("scheduleId")
                busy_list = []
                for item in entry.get("scheduleItems", []) or []:
                    s = item.get("start", {}).get("dateTime")
                    e = item.get("end", {}).get("dateTime")
                    if s and e:
                        from datetime import datetime

                        try:
                            sdt = datetime.fromisoformat(s)
                        except ValueError:
                            sdt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                        try:
                            edt = datetime.fromisoformat(e)
                        except ValueError:
                            edt = datetime.fromisoformat(e.replace("Z", "+00:00"))
                        busy_list.append(BusySlot(start=sdt, end=edt))
                calendars.append(FreeBusyCalendar(calendar=name, busy=tuple(busy_list)))
            return FreeBusyResult(status="success", calendars=tuple(calendars))
        except Exception as e:
            logger.exception("Microsoft getSchedule failed")
            return FreeBusyResult(status="error", error={"message": str(e)})
