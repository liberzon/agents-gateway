from typing import List, Literal, Optional

from ..models import EventCreateRequest, EventResult, FreeBusyRequest, FreeBusyResult
from ..providers.calendar_base import CalendarProvider
from ..providers.freebusy_base import FreeBusyProvider
from ..utils import parse_dt


class CalendarService:
    """
    Unified calendar service facade.
    Provides both event management (CRUD) and availability queries (Free/Busy).
    Standardized interface across Google and Microsoft calendar providers.
    """

    def __init__(self, calendar_provider: CalendarProvider, freebusy_provider: Optional[FreeBusyProvider] = None):
        """
        Initialize calendar service with providers.

        Args:
            calendar_provider: Provider for event CRUD operations
            freebusy_provider: Optional provider for availability queries
        """
        self.calendar = calendar_provider
        self.freebusy = freebusy_provider

    # ---------- Create ----------
    def create_event(
        self,
        *,
        token: str,
        calendar_id: str,
        req: EventCreateRequest,
        default_timezone: str = "UTC",
    ) -> EventResult:
        return self.calendar.create_event(
            token=token,
            calendar_id=calendar_id,
            req=req,
            default_timezone=req.timezone or default_timezone,
        )

    # ---------- Update ----------
    def update_event(
        self,
        *,
        token: str,
        calendar_id: str,
        event_id: str,
        patch: dict,
    ) -> EventResult:
        return self.calendar.update_event(
            token=token,
            calendar_id=calendar_id,
            event_id=event_id,
            patch=patch,
        )

    # ---------- Cancel ----------
    def cancel_event(
        self,
        *,
        token: str,
        calendar_id: str,
        event_id: str,
        send_updates: Literal["all", "externalOnly", "none"] = "all",
    ) -> EventResult:
        return self.calendar.cancel_event(
            token=token,
            calendar_id=calendar_id,
            event_id=event_id,
            send_updates=send_updates,
        )

    # ---------- List ----------
    def list_events(
        self,
        *,
        token: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        q: Optional[str] = None,
        max_results: int = 100,
    ) -> List[EventResult]:
        """
        Lists events in a calendar.
        - time_min/time_max: ISO 8601 strings or None.
        """
        tmin = parse_dt(time_min) if time_min else None
        tmax = parse_dt(time_max) if time_max else None
        return self.calendar.list_events(
            token=token,
            calendar_id=calendar_id,
            time_min=tmin,
            time_max=tmax,
            q=q,
            max_results=max_results,
        )

    # ---------- Free/Busy ----------
    def query_freebusy(
        self,
        *,
        token: str,
        req: FreeBusyRequest,
        default_timezone: str = "UTC",
    ) -> FreeBusyResult:
        """
        Query availability across multiple calendars.

        Args:
            token: OAuth2 access token
            req: Free/busy request with calendars and time range
            default_timezone: Default timezone if not specified in request

        Returns:
            FreeBusyResult with busy time slots per calendar

        Raises:
            ValueError: If freebusy_provider was not configured
        """
        if not self.freebusy:
            raise ValueError(
                "Free/busy functionality not available. "
                "Pass a FreeBusyProvider to CalendarService.__init__() to enable this feature."
            )
        return self.freebusy.query_freebusy(token=token, req=req, default_timezone=default_timezone)
