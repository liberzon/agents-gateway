import logging
from typing import Optional, Tuple

import httpx

from ..config import ProviderConfig
from ..models import BusySlot, FreeBusyCalendar, FreeBusyRequest, FreeBusyResult
from ..utils import json_or_text, parse_dt, timeout_obj

logger = logging.getLogger(__name__)


class GoogleFreeBusyProvider:
    def __init__(self, config: ProviderConfig, http: Optional[httpx.Client] = None):
        self.config = config
        self.http = http
        self.base_url = config.base_url or "https://www.googleapis.com/calendar/v3"

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
        url = f"{self.base_url}/freeBusy"
        payload = {
            "timeMin": req.time_min.isoformat(),
            "timeMax": req.time_max.isoformat(),
            "timeZone": tz,
            "items": [{"id": c} for c in req.calendars],
        }
        try:
            client = self._client(http_timeout)
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return FreeBusyResult(status="error", error=json_or_text(resp))
            data = resp.json()
            calendars = []
            for cal_id, cal in (data.get("calendars") or {}).items():
                busy_list = []
                for p in cal.get("busy", []):
                    start = parse_dt(p.get("start"))
                    end = parse_dt(p.get("end"))
                    busy_list.append(BusySlot(start=start, end=end))
                calendars.append(FreeBusyCalendar(calendar=cal_id, busy=tuple(busy_list)))
            return FreeBusyResult(status="success", calendars=tuple(calendars))
        except Exception as e:
            logger.exception("Google freeBusy failed")
            return FreeBusyResult(status="error", error={"message": str(e)})
