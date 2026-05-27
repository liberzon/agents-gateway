"""
Calendar Toolkit

This module provides the CalendarToolkit class for multi-provider
calendar management with support for Google Calendar and Microsoft Calendar.

Usage:
    >>> from toolkits.calendar import CalendarToolkit
    >>> toolkit = CalendarToolkit(
    ...     user_id="user123",
    ...     organizer_email="user@example.com",
    ...     service_name="google_calendar",
    ...     auth=True
    ... )
    >>> # Use with Agno agent
    >>> from agno.agent import Agent
    >>> agent = Agent(tools=[toolkit])
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import dateparser
from agno.tools import Toolkit

from toolkits.base import BaseToolkit
from workspace_suite import CalendarService
from workspace_suite.config import ProviderConfig, get_system_timezone
from workspace_suite.models import Attendee, BusySlot, EventCreateRequest, EventResult, FreeBusyRequest, FreeBusyResult
from workspace_suite.providers.google_calendar import GoogleCalendarProvider
from workspace_suite.providers.google_freebusy import GoogleFreeBusyProvider
from workspace_suite.providers.microsoft_calendar import MicrosoftCalendarProvider
from workspace_suite.providers.microsoft_freebusy import MicrosoftFreeBusyProvider

logger = logging.getLogger(__name__)


# ---------------------------
# Exceptions
# ---------------------------
class ContactsAuthError(RuntimeError):
    """Exception raised when calendar authentication fails."""

    pass


# ---------------------------
# Helper Functions (Module-Level)
# ---------------------------
def _first_not_none(*vals):
    """Return the first non-None value from arguments."""
    for v in vals:
        if v is not None:
            return v
    return None


def _normalize_event_kwargs(
    *,
    summary: Optional[str] = None,
    title: Optional[str] = None,
    start: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    attendees: Optional[List[str]] = None,
    timezone_str: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    send_updates: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize event creation arguments."""
    return {
        "summary": _first_not_none(summary, title, "Untitled Meeting"),
        "start": _first_not_none(start),
        "duration_minutes": duration_minutes,
        "attendees": _first_not_none(attendees) or [],
        "timezone_str": timezone_str,  # Will be resolved later with self.default_timezone
        "location": location,
        "description": description,
        "send_updates": send_updates,
    }


# ---------------------------
# Token Fetching (to be imported from main app)
# ---------------------------
# Note: This will be imported from test_cards_app3.py when the toolkit is used
# For standalone usage, you need to provide a fetch_access_token function


# ---------------------------
# Calendar Toolkit
# ---------------------------
class CalendarToolkit(BaseToolkit):
    """
    AI Agent toolkit for calendar management operations with multi-provider support.

    This toolkit provides intelligent calendar scheduling capabilities for AI agents,
    supporting both Google Calendar and Microsoft Calendar. It handles OAuth
    authentication, token management, meeting creation, and provides graceful
    fallbacks when authentication is unavailable.

    ARCHITECTURE
    ============
    The toolkit follows a confirmation-based workflow where the AI agent proposes
    meeting details, the user reviews and confirms, and then the meeting is created.
    This prevents unwanted calendar modifications and allows users to edit details
    before committing.

    Token Management:
    -----------------
    - Uses a shared TokenCache (toolkits.token_cache) for efficient token storage across instances
    - Supports multiple calendar providers (Google, Microsoft) via service_name parameter
    - Tokens are cached with TTL-based expiration (default: 5 minutes)
    - Automatic token refresh and error handling with cooldown periods

    Authentication Flow:
    -------------------
    1. If user has valid token → toolkit provides schedule_meeting tool
    2. If no valid token → toolkit provides auth_required tool
    3. Pre-hook (create_calendar_toolkit_selector) dynamically selects active toolkit
    4. User authenticates via OAuth flow when prompted
    5. Subsequent requests automatically use authenticated service

    SUPPORTED SERVICES
    ==================
    - Google Calendar (service_name="google_calendar")
    - Microsoft Calendar (service_name="microsoft_calendar")

    TOOLS PROVIDED
    ==============
    When authenticated (auth=True):
    - schedule_meeting: Create calendar events with confirmation workflow
    - error_card: Display error messages with retry options

    When not authenticated (auth=False):
    - auth_required: Prompt user to authenticate calendar service

    CONFIRMATION WORKFLOW
    =====================
    The schedule_meeting tool is marked as requires_confirmation_tools, which triggers:
    1. Agent calls schedule_meeting with proposed meeting details
    2. Run pauses and returns tool call details to client
    3. Client displays interactive form for user to review/edit
    4. User confirms, skips, or cancels
    5. Client sends confirmed tools via /chat/commit endpoint
    6. Agent resumes and executes the actual calendar API call
    7. Meeting is created and confirmation is returned

    USAGE EXAMPLES
    ==============
    Basic initialization:
        >>> toolkit = CalendarToolkit(
        ...     user_id="user123",
        ...     organizer_email="user@example.com",
        ...     service_name="google_calendar",
        ...     auth=True
        ... )

    Multi-provider setup with dynamic selection:
        >>> google_toolkit = CalendarToolkit(
        ...     user_id="user123",
        ...     organizer_email="user@example.com",
        ...     service_name="google_calendar"
        ... )
        >>> microsoft_toolkit = CalendarToolkit(
        ...     user_id="user123",
        ...     organizer_email="user@example.com",
        ...     service_name="microsoft_calendar"
        ... )
        >>> # Pre-hook will select appropriate toolkit based on token availability

    No-auth fallback:
        >>> no_auth_toolkit = CalendarToolkit(
        ...     user_id="user123",
        ...     organizer_email="user@example.com",
        ...     service_name="calendar",
        ...     auth=False
        ... )

    CLASS ATTRIBUTES
    ================
    calendar_id : str
        Default calendar identifier for API calls (default: "primary")

    default_timezone : str
        Default timezone for meetings (defaults to system timezone if not provided)

    http_timeout_s : float
        HTTP request timeout in seconds (default: 15.0)

    INSTANCE ATTRIBUTES
    ===================
    user_id : str
        User identifier for token lookup and attribution

    organizer_email : str
        Email address of the meeting organizer (automatically added to attendees)

    service_name : str
        Calendar service identifier ("google_calendar", "microsoft_calendar", etc.)

    context : Dict[str, Any]
        Runtime context including token_valid status

    METHODS
    =======
    Public Tools:
    - schedule_meeting(): Create calendar events (requires confirmation)
    - calendar_auth_required(): Prompt for calendar authentication
    - error_card(): Display error messages

    Internal Helpers:
    - _prepare_auth(): Manage OAuth token retrieval and validation

    ERROR HANDLING
    ==============
    - ContactsAuthError: Token fetch failures, expired tokens
    - HTTP errors: API quota limits, permission issues, network failures
    - Validation errors: Invalid datetime formats, missing required fields

    All errors are caught and returned as structured error cards with retry options.

    SECURITY
    ========
    - Tokens never exposed in logs or responses
    - OAuth scopes limited to calendar.events (no full account access)
    - User confirmation required before any calendar modifications
    - Service account authentication for backend token storage

    INTEGRATION
    ===========
    This toolkit is designed to work with:
    - Agno 2.0 Agent framework
    - FastAPI backend with /chat and /chat/commit endpoints
    - Rich-formatted CLI client for interactive confirmations
    - Backend token service for OAuth token management

    SEE ALSO
    ========
    - TokenCache: Shared token caching system (toolkits.token_cache)
    - fetch_access_token(): Module-level token fetcher (must be provided by application)
    - create_calendar_toolkit_selector(): Pre-hook for dynamic toolkit selection
    """

    calendar_id = "primary"
    http_timeout_s = 15.0

    def __init__(
        self,
        user_id: str,
        organizer_email: str,
        service_name: str,
        auth: bool = True,
        fetch_token_func=None,
        agent_user_id: Optional[str] = None,
        agent_session_id: Optional[str] = None,
        default_timezone: Optional[str] = None,
    ):
        """
        Initialize the CalendarToolkit.

        Args:
            user_id: User identifier for token lookup (tools_user_id)
            organizer_email: Email address of the meeting organizer
            service_name: Calendar service name ("google_calendar", "microsoft_calendar", etc.)
            auth: Whether user is authenticated (determines which tools are available)
            fetch_token_func: Optional function to fetch access tokens. If not provided,
                            toolkit will attempt to import from parent module.
            agent_user_id: Optional agent user id for schedule links
            agent_session_id: Optional agent session id for schedule links
        """
        # Store calendar-specific attributes FIRST (needed by _initialize_service)
        self.organizer_email = organizer_email
        self.agent_user_id = agent_user_id
        self.agent_session_id = agent_session_id
        self.default_timezone = default_timezone if default_timezone is not None else get_system_timezone()

        # Call BaseToolkit.__init__ which will call _initialize_service()
        BaseToolkit.__init__(self, user_id, service_name, auth, fetch_token_func)

        # Build tools list AFTER service is initialized (methods need self.calendar_service)
        tools_list: list = []
        confirmation_tools_list = []

        if auth:
            tools_list.append(self.schedule_meeting)
            tools_list.append(self.schedule_meeting_find_time)
            tools_list.append(self.cancel_meeting)
            tools_list.append(self.list_events)
            confirmation_tools_list = ["schedule_meeting", "schedule_meeting_find_time", "cancel_meeting"]
        else:
            tools_list.append(self.calendar_auth_required)

        # Call Toolkit base class __init__ LAST with complete tools list
        Toolkit.__init__(
            self,
            name="calendar_toolkit",
            tools=tools_list,
            requires_confirmation_tools=confirmation_tools_list,
            show_result_tools=[],
            stop_after_tool_call_tools=([] if auth else ["calendar_auth_required"]),
        )

    def _initialize_service(self) -> None:
        """Initialize CalendarService with appropriate provider based on service_name."""
        config = ProviderConfig(default_timezone=self.default_timezone)

        if self.service_name == "google_calendar":
            calendar_provider = GoogleCalendarProvider(config)
            freebusy_provider = GoogleFreeBusyProvider(config)
        elif self.service_name == "microsoft_calendar":
            calendar_provider = MicrosoftCalendarProvider(config)  # type: ignore[assignment]
            freebusy_provider = MicrosoftFreeBusyProvider(config)  # type: ignore[assignment]
        else:
            # Fallback to google for backward compatibility
            calendar_provider = GoogleCalendarProvider(config)
            freebusy_provider = GoogleFreeBusyProvider(config)

        self.calendar_service = CalendarService(calendar_provider, freebusy_provider)

    # noinspection PyMethodMayBeStatic
    def _parse_attendees_from_strings(self, attendees: Optional[List[str]]) -> List[Attendee]:
        """
        Parse string attendees to Attendee objects.
        Supports "name email" or just "email" format.

        Args:
            attendees: List of attendee strings in "name email" or "email" format

        Returns:
            List of Attendee objects
        """
        result = []
        for raw in attendees or []:
            parts = raw.split()
            if len(parts) == 2:
                name, email = parts
                result.append(Attendee(name=name, email=email))
            else:
                # Just email provided
                result.append(Attendee(name=None, email=raw))
        return result

    def _ensure_organizer_in_attendees(self, attendees: List[Attendee]) -> List[Attendee]:
        """
        Add organizer to attendees if not already present.
        Preserves existing behavior of auto-adding organizer.

        Args:
            attendees: List of Attendee objects

        Returns:
            List of Attendee objects with organizer included
        """
        if not self.organizer_email:
            return attendees

        # Check if organizer already in list
        if any(a.email.lower() == self.organizer_email.lower() for a in attendees):
            return attendees

        # Add organizer
        return attendees + [Attendee(name="Organizer", email=self.organizer_email)]

    def _parse_datetime(self, s: str | datetime) -> datetime:
        """
        Parse datetime string using natural language or ISO format.

        Supports both ISO 8601 format and natural language expressions like:
        - "tomorrow", "next week", "in 2 hours"
        - "Friday at 3pm", "next Monday 2pm"
        - ISO strings: "2025-10-22T14:00:00Z", "2025-10-22"

        Uses the user's timezone from self.default_timezone for interpretation.

        Args:
            s: Either a datetime string (natural language or ISO format) or a datetime object

        Returns:
            datetime object with timezone (defaults to user's timezone if not specified)

        Fallback:
            Returns datetime.now(user_timezone) if string parsing fails
        """
        user_tz = ZoneInfo(self.default_timezone)

        # If already a datetime object, ensure it has timezone info
        if isinstance(s, datetime):
            if s.tzinfo is None:
                return s.replace(tzinfo=user_tz)
            return s

        # Use dateparser for NLP support (handles both natural language and ISO format)
        dt = dateparser.parse(  # type: ignore[no-untyped-call,misc]
            s,
            settings={
                "TIMEZONE": self.default_timezone,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(user_tz),
            },
        )

        # Fallback to current time if parsing fails
        return dt if dt else datetime.now(user_tz)

    def _fmt_rfc3339(self, dt: datetime) -> str:
        """
        Format datetime as RFC3339 string.
        Uses user's timezone as default for naive datetimes, then converts to UTC for RFC3339 output.

        Args:
            dt: datetime object to format

        Returns:
            RFC3339 datetime string in UTC (ends with 'Z')
        """
        user_tz = ZoneInfo(self.default_timezone)

        if dt.tzinfo is None:
            # Naive datetime - interpret as user's timezone, then convert to UTC
            dt = dt.replace(tzinfo=user_tz)

        # Convert to UTC and format as RFC3339
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    # noinspection PyMethodMayBeStatic
    def _event_result_to_dict(self, result: EventResult) -> Dict[str, Any]:
        """
        Convert EventResult to dict for backward compatibility.
        Maintains existing return format expected by toolkit consumers.

        Args:
            result: EventResult dataclass from workspace_suite

        Returns:
            Dict with status, event details, or error information
        """
        if result.status == "error":
            return {
                "status": "error",
                "error": result.error or {"message": "Unknown error"},
                "summary": result.summary,
                "start": self._fmt_rfc3339(result.start) if result.start else None,
                "end": self._fmt_rfc3339(result.end) if result.end else None,
                "attendees": [{"displayName": a.name or a.email, "email": a.email} for a in result.attendees],
                "location": result.location,
                "timezone": result.timezone,
            }

        return {
            "status": "success",
            "event_id": result.event_id or "",
            "html_link": result.html_link or "",
            "conference_link": result.conference_link,  # NEW: Google Meet link
            "summary": result.summary,
            "start": self._fmt_rfc3339(result.start) if result.start else None,
            "end": self._fmt_rfc3339(result.end) if result.end else None,
            "attendees": [{"displayName": a.name or a.email, "email": a.email} for a in result.attendees],
            "location": result.location,
            "timezone": result.timezone,
        }

    def _build_schedule_link(
        self,
        start: str,
        summary: str,
        attendees: List[str],
        duration_minutes: int,
        timezone_str: str,
    ) -> str:
        """
        Build a /toolkit/run URL for scheduling a meeting at a specific time.

        Args:
            start: RFC3339 datetime string for meeting start
            summary: Meeting title/summary
            attendees: List of attendee email addresses
            duration_minutes: Meeting duration in minutes
            timezone_str: Timezone for the meeting

        Returns:
            URL containing Jinja2 template that will be filled in the front-end for /toolkit/run endpoint
        """

        # Build query parameters - all required toolkit/run parameters
        params = {
            "toolkit_name": "CalendarToolkit",
            "method_name": "schedule_meeting",
            "agent_user_id": self.agent_user_id or "unknown",
            "agent_session_id": self.agent_session_id or "unknown",
            "tools_user_id": self.user_id,
            "organizer_email": self.organizer_email,
            "summary": summary,
            "start": start,
            "duration_minutes": str(duration_minutes),
            "timezone_str": timezone_str,
            "skip_confirmation": "true",
            "conference": "false",
        }

        # URL-encode single-value parameters
        encoded_params = urlencode(params)

        # Add multi-value attendees parameter
        attendee_params = [("attendees", email) for email in attendees]
        encoded_attendees = urlencode(attendee_params)

        # Combine all parameters
        if encoded_attendees:
            query_string = f"{encoded_params}&{encoded_attendees}"
        else:
            query_string = encoded_params

        return f"{{{{toolkit_run_base_url}}}}/toolkit/run?{query_string}"

    def _build_cancel_link(self, event_id: str) -> str:
        """
        Build a /toolkit/run URL for canceling a calendar event.

        Args:
            event_id: Calendar event ID to cancel

        Returns:
            Fully-formed URL for /toolkit/run endpoint to cancel the event
        """

        # Build query parameters - all required toolkit/run parameters
        params = {
            "toolkit_name": "CalendarToolkit",
            "method_name": "cancel_meeting",
            "agent_user_id": self.agent_user_id or "unknown",
            "agent_session_id": self.agent_session_id or "unknown",
            "tools_user_id": self.user_id,
            "organizer_email": self.organizer_email,
            "event_id": event_id,
            "skip_confirmation": "true",
        }

        # URL-encode parameters
        query_string = urlencode(params)

        return f"{{{{toolkit_run_base_url}}}}/toolkit/run?{query_string}"

    # noinspection PyMethodMayBeStatic
    def _find_available_slots(
        self,
        freebusy_result: FreeBusyResult,
        duration_minutes: int,
        search_start: datetime,
        search_end: datetime,
        working_hours_start: int = 9,
        working_hours_end: int = 18,
        summary: str = "Meeting",
        attendees: Optional[List[str]] = None,
        timezone_str: str = "Asia/Jerusalem",
    ) -> List[Dict[str, str]]:
        """
        Find available time slots from freebusy result.

        This method processes the freebusy data to identify common available time slots
        across all attendees. It filters slots to working hours only and skips weekends.

        Args:
            freebusy_result: FreeBusyResult from query_freebusy
            duration_minutes: Required meeting duration in minutes
            search_start: Start of search period
            search_end: End of search period
            working_hours_start: Start of working day (hour in 24h format)
            working_hours_end: End of working day (hour in 24h format)
            summary: Meeting title for schedule links
            attendees: List of attendee emails for schedule links
            timezone_str: Timezone for schedule links

        Returns:
            List of available time slots as dicts with "start", "end", and "schedule_link"
        """
        if freebusy_result.status == "error":
            return []

        # Merge all busy periods across all attendees
        all_busy: List[BusySlot] = []
        for cal in freebusy_result.calendars:
            all_busy.extend(cal.busy)

        # Sort busy periods by start time
        all_busy.sort(key=lambda slot: slot.start)

        # Merge overlapping busy periods
        merged_busy: List[BusySlot] = []
        for busy_slot in all_busy:
            if not merged_busy or busy_slot.start > merged_busy[-1].end:
                # No overlap, add new slot
                merged_busy.append(busy_slot)
            else:
                # Overlap detected, extend the last slot
                last_slot = merged_busy[-1]
                merged_busy[-1] = BusySlot(start=last_slot.start, end=max(last_slot.end, busy_slot.end))

        # Find free slots between busy periods
        available_slots: List[Dict[str, str]] = []
        current_time = search_start

        for busy_slot in merged_busy:
            # Check if there's a gap before this busy slot
            if current_time < busy_slot.start:
                # Find slots in the gap
                gap_slots = self._find_slots_in_range(
                    current_time,
                    busy_slot.start,
                    duration_minutes,
                    working_hours_start,
                    working_hours_end,
                    summary,
                    attendees or [],
                    timezone_str,
                )
                available_slots.extend(gap_slots)

            # Move current_time past this busy slot
            current_time = max(current_time, busy_slot.end)

        # Check for slots after the last busy period
        if current_time < search_end:
            gap_slots = self._find_slots_in_range(
                current_time,
                search_end,
                duration_minutes,
                working_hours_start,
                working_hours_end,
                summary,
                attendees or [],
                timezone_str,
            )
            available_slots.extend(gap_slots)

        return available_slots

    # noinspection PyMethodMayBeStatic
    def _find_slots_in_range(
        self,
        range_start: datetime,
        range_end: datetime,
        duration_minutes: int,
        working_hours_start: int,
        working_hours_end: int,
        summary: str,
        attendees: List[str],
        timezone_str: str,
    ) -> List[Dict[str, str]]:
        """
        Find available meeting slots within a time range.

        Generates time slots that:
        - Fit the required duration
        - Fall within working hours
        - Skip weekends (Saturday/Sunday)
        - Start on 30-minute intervals (9:00, 9:30, 10:00, etc.)

        Args:
            range_start: Start of the range to search
            range_end: End of the range to search
            duration_minutes: Required meeting duration
            working_hours_start: Start of working day (hour)
            working_hours_end: End of working day (hour)

        Returns:
            List of time slot dicts with "start" and "end" RFC3339 strings
        """
        slots: List[Dict[str, str]] = []
        current = range_start

        while current < range_end:
            # Skip weekends (Saturday=5, Sunday=6)
            if current.weekday() >= 5:
                # Move to next Monday 9am
                days_until_monday = 7 - current.weekday()
                current = current.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
                current = current + timedelta(days=days_until_monday)
                continue

            # Ensure we're within working hours
            if current.hour < working_hours_start:
                # Move to start of working day
                current = current.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
            elif current.hour >= working_hours_end:
                # Move to next day
                current = current.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
                current = current + timedelta(days=1)
                continue

            # Check if slot fits within range and working hours
            slot_end = current + timedelta(minutes=duration_minutes)

            # Ensure slot doesn't extend past working hours or range_end
            if slot_end.hour > working_hours_end or (slot_end.hour == working_hours_end and slot_end.minute > 0):
                # Slot would extend past working hours, move to next day
                current = current.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)
                current = current + timedelta(days=1)
                continue

            if slot_end > range_end:
                # Slot would extend past search range
                break

            # Valid slot found!
            slot_start_str = self._fmt_rfc3339(current)
            slot_end_str = self._fmt_rfc3339(slot_end)

            # Build schedule link for this slot
            schedule_link = self._build_schedule_link(
                start=slot_start_str,
                summary=summary,
                attendees=attendees or [],
                duration_minutes=duration_minutes,
                timezone_str=timezone_str,
            )

            slots.append(
                {
                    "start": slot_start_str,
                    "end": slot_end_str,
                    "schedule_link": schedule_link,
                }
            )

            # Move to next 30-minute interval
            current = current + timedelta(minutes=30)

        return slots

    # -------- Render helpers --------
    def calendar_auth_required(self) -> Dict[str, Any]:
        """
        Display an authentication required message to the user.

        This method is called when the user attempts to schedule a meeting but has not
        authenticated their calendar service (Google Calendar or Microsoft Calendar).
        It informs the user that calendar authentication is required before they can
        create, view, or manage meeting events.

        WHEN CALLED
        - Triggered by the agent when no calendar tokens are available

        USER EXPERIENCE
        The user will see a message indicating:
        - Calendar authentication is required to schedule meetings
        - Instructions to connect their Google or Microsoft Calendar account
        - Available actions: "Connect Calendar" or "Skip"

        OUTPUT (JSON)
        Returns an auth-required card:
        {
            "card": "calendar-auth-required",
            "context": {
                "token_valid": false
            }
        }
        """
        self._prepare_auth(hard=False)
        return {
            "card": "calendar-auth-required",
            "context": dict(self.context),
        }

    # -------- ENTRY + Side-effect tool --------
    def schedule_meeting(
        self,
        start: str | datetime,
        summary: str = "Untitled Meeting",
        timezone_str: Optional[str] = None,
        attendees: Optional[List[str | Dict[str, str]]] = None,
        location: Optional[str] = None,
        duration_minutes: int = 30,
        description: Optional[str] = "Scheduled via Assistant",
        send_updates: str = "all",
        conference: bool = False,
        end: Optional[str | datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create and schedule a meeting using workspace_suite CalendarService.

        ADAPTER METHOD: This method converts toolkit-style string inputs to workspace_suite
        typed models (EventCreateRequest) and calls CalendarService.create_event().

        The method preserves backward-compatible behavior:
        - Parses "name email" or "email" string attendees
        - Automatically adds organizer to attendees if missing
        - Calculates end time from duration_minutes
        - Returns dict format for toolkit consumers

        ARGUMENTS:
            start (str | datetime): Start datetime for the meeting. Can be:
                - ISO 8601 datetime string (e.g., "2025-10-22T14:00:00Z")
                - datetime object (timezone-aware recommended, defaults to UTC if naive)
            summary (str, default="Untitled Meeting"): Title of the meeting.
            timezone_str (str, default="Asia/Jerusalem"): Timezone for the event.
            attendees (Optional[List[str | Dict[str, str]]], default=None): List of attendees in one of these formats:
                - String format: `"name email"` or `"email"` (e.g., "alice@example.com")
                - Dict format: `{"email": "alice@example.com"}` (Gemini format)
                The authenticated user is added if missing.
            location (Optional[str], default=None): Location/address for the meeting.
            duration_minutes (int, default=30): Meeting duration in minutes. Used to calculate `end` time
                if `end` parameter is not provided.
            description (str, default="Scheduled via Assistant"): Description/agenda text.
            send_updates (str, default="all"): Calendar API `sendUpdates` mode.
                Options: `"all"`, `"externalOnly"`, `"none"`.
            conference (bool, default=False): Whether to create a Google Meet conference link.
            end (Optional[str | datetime], default=None): End datetime for the meeting. Can be:
                - ISO 8601 datetime string (e.g., "2025-10-22T15:00:00Z")
                - datetime object (timezone-aware recommended, defaults to UTC if naive)
                If not provided, calculated as `start + duration_minutes`.

        OUTPUT (JSON)
        - On success:
          {
            "status":"success",
            "event_id":"...",
            "html_link":"...",
            "conference_link":"...",  # NEW: Google Meet link (if conference=True)
            "summary":"...",
            "start":"...",
            "end":"...",
            "attendees":[...],
            "location":"...",
            "timezone":"Asia/Jerusalem"
          }
        - On failure:
          - Returns result with "Scheduling failed…" and actions ["retry","cancel"].
        """
        try:
            token = self._prepare_auth(hard=True)
        except ContactsAuthError as e:
            logger.warning(f"[Meeting] Cannot schedule: auth required ({e})")
            self.context["token_valid"] = False
            return self.error_card("Calendar authentication failed. Please reconnect and retry.")

        if not token:
            return self.error_card("Calendar authentication failed. No valid token available.")

        # Convert string start to datetime
        start_dt = self._parse_datetime(start)

        # Calculate end time: use explicit end if provided and valid, otherwise calculate from duration
        if end is not None:
            end_dt = self._parse_datetime(end)
            # Validate that end is after start
            if end_dt <= start_dt:
                logger.warning(
                    f"[Meeting] Invalid end time: end ({end_dt}) is not after start ({start_dt}). "
                    f"Falling back to duration_minutes={duration_minutes}"
                )
                end_dt = start_dt + timedelta(minutes=duration_minutes)
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)

        # Normalize attendees: handle both string format and dict format
        normalized_attendees: List[str] = []
        if attendees:
            for att in attendees:
                if isinstance(att, dict):
                    # Extract email from dict format: {"email": "user@example.com"}
                    normalized_attendees.append(att.get("email", ""))
                else:
                    # Already a string
                    normalized_attendees.append(att)

        # Parse string attendees to Attendee objects
        attendee_objs = self._parse_attendees_from_strings(normalized_attendees)

        # Auto-add organizer if missing (preserve existing behavior)
        attendee_objs = self._ensure_organizer_in_attendees(attendee_objs)

        # Create workspace_suite request model
        req = EventCreateRequest(
            summary=summary,
            start=start_dt,
            end=end_dt,
            description=description,
            attendees=attendee_objs,
            location=location,
            timezone=timezone_str or self.default_timezone,
            conference=conference,
            send_updates=send_updates,  # type: ignore[arg-type]
        )

        # Call workspace_suite CalendarService
        result = self.calendar_service.create_event(
            token=token,
            calendar_id=self.calendar_id,
            req=req,
            default_timezone=self.default_timezone,
        )

        # Convert result to dict for backward compatibility
        return self._event_result_to_dict(result)

    def schedule_meeting_find_time(
        self,
        summary: str = "Meeting",
        attendees: Optional[List[str]] = None,
        duration_minutes: int = 30,
        search_start_date: Optional[str | datetime] = None,
        search_days: int = 3,
        timezone_str: Optional[str] = None,
        working_hours_start: int = 9,
        working_hours_end: int = 18,
    ) -> Dict[str, Any]:
        """
        Find available meeting times using calendar freebusy queries.

        This tool is called when no specific time is specified for a meeting. It searches
        for available time slots either from today or from a date requested in the user prompt.
        The tool queries calendar availability for the organizer and all specified attendees
        to find common free time slots that accommodate the meeting duration.

        WHEN TO USE THIS TOOL
        - User asks to schedule a meeting but doesn't specify a specific time
        - User wants to find available times for a meeting
        - User says "find a time for..." or "when are we all available?"
        - User requests meeting suggestions

        HOW IT WORKS
        1. Queries calendar availability for organizer + all attendees
        2. Finds time slots where everyone is free
        3. Filters to working hours (9am-6pm by default)
        4. Skips weekends (Saturday/Sunday)
        5. Returns suggested meeting times on 30-minute intervals

        ARGUMENTS:
            summary (str, default="Meeting"): Title/purpose of the meeting (for context)
            attendees (Optional[List[str]], default=None): List of attendee emails to check availability.
                Format: "name email" or just "email". Organizer is automatically included.
            duration_minutes (int, default=30): Required meeting duration in minutes
            search_start_date (Optional[str | datetime], default=None): Start date for search. Can be:
                - ISO date string (YYYY-MM-DD) or datetime string
                - datetime object
                - "today" string
                - If not specified, defaults to today.
            search_days (int, default=3): Number of working days to search ahead (skips weekends)
            timezone_str (str, default="Asia/Jerusalem"): Timezone for the search and results
            working_hours_start (int, default=9): Start of working day (hour in 24h format, 0-23)
            working_hours_end (int, default=18): End of working day (hour in 24h format, 0-23)

        OUTPUT (JSON)
        - On success:
            {
              "response_type": "suggested_meeting_times",
              "suggested_times": [
                {
                  "start": "2024-10-28T09:00:00Z",
                  "end": "2024-10-28T09:45:00Z",
                  "schedule_link": "{{toolkit_run_base_url}}/toolkit/run?toolkit_name=CalendarToolkit&method_name=schedule_meeting&agent_user_id=unknown&agent_session_id=unknown&tools_user_id=895b3648-2bec-4dc9-b036-9b28963f793d&organizer_email=yair%40experasion.ai&summary=Meeting&start=2024-10-28T09%3A00%3A00Z&duration_minutes=45&timezone_str=Asia%2FJerusalem&skip_confirmation=true&conference=false&attendees=yair%40experasion.ai&attendees=alex%40example.com"
                },
                {
                  "start": "2024-10-28T09:30:00Z",
                  "end": "2024-10-28T10:15:00Z",
                  "schedule_link": "{{toolkit_run_base_url}}/toolkit/run?toolkit_name=CalendarToolkit&method_name=schedule_meeting&agent_user_id=unknown&agent_session_id=unknown&tools_user_id=895b3648-2bec-4dc9-b036-9b28963f793d&organizer_email=yair%40experasion.ai&summary=Meeting&start=2024-10-28T09%3A30%3A00Z&duration_minutes=45&timezone_str=Asia%2FJerusalem&skip_confirmation=true&conference=false&attendees=yair%40experasion.ai&attendees=alex%40example.com"
                },
                {
                  "start": "2024-10-28T10:00:00Z",
                  "end": "2024-10-28T10:45:00Z",
                  "schedule_link": "{{toolkit_run_base_url}}/toolkit/run?toolkit_name=CalendarToolkit&method_name=schedule_meeting&agent_user_id=unknown&agent_session_id=unknown&tools_user_id=895b3648-2bec-4dc9-b036-9b28963f793d&organizer_email=yair%40experasion.ai&summary=Meeting&start=2024-10-28T10%3A00%3A00Z&duration_minutes=45&timezone_str=Asia%2FJerusalem&skip_confirmation=true&conference=false&attendees=yair%40experasion.ai&attendees=alex%40example.com"
                }
              ],
              "message": "I found these 3 morning slots next week when you and Alex are both free for 45 minutes."
            }
        - On failure:
          - Returns error_card with message

        EXAMPLE USAGE
        Agent receives: "Schedule a meeting with alice@example.com and bob@example.com next week"
        Agent calls: schedule_meeting_find_time(
            summary="Team Meeting",
            attendees=["alice@example.com", "bob@example.com"],
            duration_minutes=60,
            search_start_date="2025-10-28",  # Next Monday
            search_days=5  # Search Mon-Fri
        )
        Agent receives: List of 20+ available time slots
        Agent presents JSON that is parsed into results action card."
        """
        try:
            token = self._prepare_auth(hard=True)
        except ContactsAuthError as e:
            logger.warning(f"[FindTime] Cannot query availability: auth required ({e})")
            self.context["token_valid"] = False
            return self.error_card("Calendar authentication failed. Please reconnect and retry.")

        if not token:
            return self.error_card("Calendar authentication failed. No valid token available.")

        # Parse search_start_date (dateparser handles None, "today", and all NLP inputs)
        search_start = self._parse_datetime(search_start_date if search_start_date is not None else "today")

        # Normalize to start of working day
        search_start = search_start.replace(hour=working_hours_start, minute=0, second=0, microsecond=0)

        # Calculate search_end (search_days working days ahead, skip weekends)
        search_end = search_start
        working_days_added = 0
        while working_days_added < search_days:
            search_end = search_end + timedelta(days=1)
            # Skip weekends (Saturday=5, Sunday=6)
            if search_end.weekday() < 5:
                working_days_added += 1

        # Set end to end of working day
        search_end = search_end.replace(hour=working_hours_end, minute=0, second=0, microsecond=0)

        logger.info(f"[FindTime] Searching from {search_start} to {search_end} ({search_days} working days)")

        # Parse attendees and ensure organizer is included
        attendee_objs = self._parse_attendees_from_strings(attendees)
        attendee_objs = self._ensure_organizer_in_attendees(attendee_objs)

        # Build list of calendar IDs (email addresses)
        calendar_ids = [att.email for att in attendee_objs]

        logger.info(f"[FindTime] Checking availability for {len(calendar_ids)} attendees: {calendar_ids}")

        # Create FreeBusyRequest
        freebusy_req = FreeBusyRequest(
            calendars=calendar_ids,
            time_min=search_start,
            time_max=search_end,
            timezone=timezone_str or self.default_timezone,
            interval_minutes=30,  # Request 30-minute granularity
        )

        # Query freebusy
        try:
            freebusy_result = self.calendar_service.query_freebusy(
                token=token,
                req=freebusy_req,
                default_timezone=timezone_str or self.default_timezone,
            )
        except Exception as e:
            logger.exception("[FindTime] Freebusy query failed")
            return self.error_card(f"Failed to query calendar availability: {str(e)}")

        if freebusy_result.status == "error":
            # Extract detailed error information
            error_details = freebusy_result.error or {}  # type: ignore[union-attr]

            # Log the full error for debugging
            logger.error(f"[FindTime] Freebusy returned error: {error_details}")

            # Extract user-friendly message
            if isinstance(error_details, dict):
                # Try common error message fields
                error_msg = (
                    error_details.get("message")
                    or error_details.get("error", {}).get("message")  # type: ignore[union-attr]
                    or error_details.get("error_description")
                    or str(error_details)
                )
            else:
                error_msg = str(error_details)

            return self.error_card(f"Calendar availability query failed: {error_msg}")

        # Find available slots (pass summary and attendees for schedule links)
        attendee_emails = [att.email for att in attendee_objs]
        available_slots = self._find_available_slots(
            freebusy_result=freebusy_result,
            duration_minutes=duration_minutes,
            search_start=search_start,
            search_end=search_end,
            working_hours_start=working_hours_start,
            working_hours_end=working_hours_end,
            summary=summary,
            attendees=attendee_emails,
            timezone_str=timezone_str or self.default_timezone,
        )

        logger.info(f"[FindTime] Found {len(available_slots)} available time slots")

        # Build response
        if not available_slots:
            return {
                "status": "success",
                "suggested_times": [],
                "search_period": {"start": self._fmt_rfc3339(search_start), "end": self._fmt_rfc3339(search_end)},
                "attendees_checked": calendar_ids,
                "message": f"No available time slots found for a {duration_minutes}-minute meeting in the search period.",
                "timezone": timezone_str or self.default_timezone,
            }

        return {
            "status": "success",
            "suggested_times": available_slots,
            "search_period": {"start": self._fmt_rfc3339(search_start), "end": self._fmt_rfc3339(search_end)},
            "attendees_checked": calendar_ids,
            "message": f"Found {len(available_slots)} available time slots for a {duration_minutes}-minute meeting",
            "timezone": timezone_str or self.default_timezone,
        }

    def cancel_meeting(
        self,
        event_id: str,
        send_updates: str = "all",
    ) -> Dict[str, Any]:
        """
        Cancel a calendar event by event ID.

        This tool removes an event from the calendar and optionally notifies attendees.
        The operation is destructive and requires user confirmation before execution.

        WHEN TO USE THIS TOOL
        - User wants to delete or cancel a specific calendar event
        - User says "cancel the meeting" or "delete this event"
        - User provides an event_id from list_events output

        ARGUMENTS:
            event_id (str): The calendar event ID to cancel (required)
            send_updates (str, default="all"): Notification mode for attendees.
                Options:
                - "all": Send cancellation notifications to all attendees
                - "externalOnly": Send only to non-organizer attendees
                - "none": Don't send any notifications

        OUTPUT (JSON)
        - On success:
          {
            "status": "success",
            "event_id": "abc123",
            "summary": "Team Meeting",
            "message": "Event canceled successfully"
          }
        - On failure:
          {
            "status": "error",
            "error": {"message": "Event not found"},
            "message": "Failed to cancel event"
          }

        EXAMPLE USAGE
        Agent receives: "Cancel the team meeting at 2pm"
        Agent first calls: list_events() to find the event
        Agent finds: event_id="abc123" for "Team Meeting" at 2pm
        Agent calls: cancel_meeting(event_id="abc123")
        User confirms deletion (via confirmation workflow)
        Event is canceled and attendees are notified
        """
        try:
            token = self._prepare_auth(hard=True)
        except ContactsAuthError as e:
            logger.warning(f"[CancelMeeting] Cannot cancel: auth required ({e})")
            self.context["token_valid"] = False
            return self.error_card("Calendar authentication failed. Please reconnect and retry.")

        if not token:
            return self.error_card("Calendar authentication failed. No valid token available.")

        logger.info(f"[CancelMeeting] Canceling event_id={event_id}, send_updates={send_updates}")

        # First, fetch event details before canceling
        event_details: Dict[str, Any] = {}
        try:
            import httpx

            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://www.googleapis.com/calendar/v3/calendars/{self.calendar_id}/events/{event_id}"

            client = httpx.Client(timeout=15.0)
            get_resp = client.get(url, headers=headers)

            if get_resp.status_code == 200:
                event_data = get_resp.json()

                # Extract event details
                summary = event_data.get("summary", "")
                start = event_data.get("start", {}).get("dateTime") or event_data.get("start", {}).get("date", "")
                end = event_data.get("end", {}).get("dateTime") or event_data.get("end", {}).get("date", "")
                location = event_data.get("location", "")
                attendees = [att.get("email", "") for att in event_data.get("attendees", [])]
                organizer = event_data.get("organizer", {}).get("email", "")

                event_details = {
                    "summary": summary,
                    "start": start,
                    "end": end,
                    "location": location,
                    "attendees": attendees,
                    "organizer": organizer,
                }
            else:
                logger.warning(f"Failed to fetch event details before canceling: {get_resp.status_code}")
        except Exception as e:
            logger.warning(f"Failed to fetch event details before canceling {event_id}: {e}")

        # Call workspace_suite CalendarService
        try:
            result = self.calendar_service.cancel_event(
                token=token,
                calendar_id=self.calendar_id,
                event_id=event_id,
                send_updates=send_updates,  # type: ignore[arg-type]
            )
        except Exception as e:
            logger.exception(f"[CancelMeeting] Failed to cancel event {event_id}")
            return self.error_card(f"Failed to cancel event: {str(e)}")

        # Convert result to dict
        result_dict = self._event_result_to_dict(result)

        if result_dict.get("status") == "success":
            # Include event details in response
            result_dict["message"] = "Event canceled successfully"
            result_dict.update(event_details)  # Add event details if available
            logger.info(f"[CancelMeeting] Successfully canceled event {event_id}")
        else:
            logger.error(f"[CancelMeeting] Failed to cancel event {event_id}: {result_dict.get('error')}")

        return result_dict

    def list_events(
        self,
        start_date: Optional[str | datetime] = None,
        days_ahead: int = 2,
        max_results: int = 10,
        search_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List calendar events.

        This tool retrieves events from the user's calendar within a specified time range.
        Each event includes both an html_link (to view in calendar) and a cancel_link
        (for one-click cancellation via the app).

        WHEN TO USE THIS TOOL
        - User asks "what meetings do I have today/tomorrow/this week?"
        - User wants to see their upcoming schedule or past schedule
        - User needs to find a specific event to cancel or modify
        - User asks "show me my calendar" or "list my events"

        ARGUMENTS:
            start_date (Optional[str | datetime], default=None): Start datetime for search. Can be:
                - ISO 8601 datetime string (e.g., "2025-10-22", "2025-10-22T09:00:00Z")
                - datetime object
                - "today" string
                - If None, defaults to now.
            days_ahead (int, default=2): Number of days to search ahead from start_date
            max_results (int, default=10): Maximum number of events to return
            search_query (Optional[str], default=None): Optional text search filter (searches
                summary, description, location, and attendee fields)

        OUTPUT (JSON)
        - On success:
          {
            "status": "success",
            "events": [
              {
                "event_id": "abc123",
                "summary": "Team Meeting",
                "start": "2025-10-22T14:00:00Z",
                "end": "2025-10-22T15:00:00Z",
                "location": "Conference Room A",
                "attendees": [
                  {"displayName": "Alice", "email": "alice@example.com"},
                  {"displayName": "Bob", "email": "bob@example.com"}
                ],
                "html_link": "https://calendar.google.com/event?eid=...",
                "cancel_link": "http://localhost:8080/toolkit/run?toolkit_name=CalendarToolkit&method_name=cancel_meeting&event_id=abc123&...",
                "timezone": "Asia/Jerusalem"
              },
              ...
            ],
            "count": 5,
            "search_period": {
              "from": "2025-10-22T09:00:00Z",
              "to": "2025-10-24T09:00:00Z"
            }
          }
        - On failure:
          {
            "status": "error",
            "error": {"message": "Failed to list events"},
            "message": "Calendar query failed"
          }

        EXAMPLE USAGE
        Agent receives: "What meetings do I have today?"
        Agent calls: list_events(start_date="today", days_ahead=1)
        Agent receives: List of today's events with links
        Agent presents: "You have 3 meetings today: [event list with cancel links]"

        USER RECEIVES TWO LINKS PER EVENT:
        1. html_link: Opens event in Google/Microsoft Calendar (external)
        2. cancel_link: One-click cancel URL containing Jinja2 template that will be filled in the front-end (internal)
        """
        try:
            token = self._prepare_auth(hard=True)
        except ContactsAuthError as e:
            logger.warning(f"[ListEvents] Cannot list: auth required ({e})")
            self.context["token_valid"] = False
            return self.error_card("Calendar authentication failed. Please reconnect and retry.")

        if not token:
            return self.error_card("Calendar authentication failed. No valid token available.")

        # Parse start_date (dateparser handles None, "today", and all NLP inputs)
        time_min_dt = self._parse_datetime(start_date if start_date is not None else "today")

        # Calculate time_max
        time_max_dt = time_min_dt + timedelta(days=days_ahead)

        # Convert to RFC3339 strings for workspace_suite
        time_min_str = self._fmt_rfc3339(time_min_dt)
        time_max_str = self._fmt_rfc3339(time_max_dt)

        logger.info(
            f"[ListEvents] Listing events from {time_min_str} to {time_max_str}, "
            f"max_results={max_results}, search_query={search_query}"
        )

        # Call workspace_suite CalendarService
        try:
            event_results = self.calendar_service.list_events(
                token=token,
                calendar_id=self.calendar_id,
                time_min=time_min_str,
                time_max=time_max_str,
                q=search_query,
                max_results=max_results,
            )
        except Exception as e:
            logger.exception("[ListEvents] Failed to list events")
            return self.error_card(f"Failed to list calendar events: {str(e)}")

        # Convert event results to dicts and add cancel_link
        events = []
        for result in event_results:
            if result.status == "error":
                logger.warning(f"[ListEvents] Skipping event with error: {result.error}")
                continue

            event_dict = {
                "event_id": result.event_id or "",
                "summary": result.summary,
                "start": self._fmt_rfc3339(result.start) if result.start else None,
                "end": self._fmt_rfc3339(result.end) if result.end else None,
                "location": result.location,
                "attendees": [{"displayName": a.name or a.email, "email": a.email} for a in result.attendees],
                "html_link": result.html_link or "",
                "cancel_link": self._build_cancel_link(result.event_id or ""),
                "timezone": result.timezone,
            }

            # Add conference_link if present
            if result.conference_link:
                event_dict["conference_link"] = result.conference_link

            events.append(event_dict)

        logger.info(f"[ListEvents] Found {len(events)} events")

        return {
            "status": "success",
            "events": events,
            "count": len(events),
            "search_period": {"from": time_min_str, "to": time_max_str},
        }


__all__ = [
    "CalendarToolkit",
    "ContactsAuthError",
]
