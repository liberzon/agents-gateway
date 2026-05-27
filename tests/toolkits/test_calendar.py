import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from agno.tools import Toolkit

from toolkits.calendar import (
    CalendarToolkit,
    ContactsAuthError,
    _first_not_none,
    _normalize_event_kwargs,
)


class TestCalendarHelpers(unittest.TestCase):
    """Test suite for calendar helper functions."""

    def setUp(self):
        """Set up test toolkit instance for testing instance methods."""
        fetch_token = Mock(return_value="test_token")
        self.toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
            default_timezone="UTC",  # Use UTC for predictable test results
        )

    def test_parse_datetime_iso_format(self):
        """Test parsing ISO format datetime strings."""
        dt = self.toolkit._parse_datetime("2024-10-22T14:30:00Z")
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 10)
        self.assertEqual(dt.day, 22)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)
        self.assertIsNotNone(dt.tzinfo)

    def test_parse_datetime_with_timezone(self):
        """Test parsing datetime with timezone offset."""
        dt = self.toolkit._parse_datetime("2024-10-22T14:30:00+02:00")
        self.assertEqual(dt.year, 2024)
        self.assertIsNotNone(dt.tzinfo)

    def test_parse_datetime_invalid_format(self):
        """Test parsing invalid datetime returns current time."""
        dt = self.toolkit._parse_datetime("invalid")
        # Should return current time
        self.assertIsInstance(dt, datetime)
        self.assertIsNotNone(dt.tzinfo)

    def test_fmt_rfc3339(self):
        """Test formatting datetime as RFC3339 string."""
        dt = datetime(2024, 10, 22, 14, 30, 0, tzinfo=timezone.utc)
        formatted = self.toolkit._fmt_rfc3339(dt)
        self.assertEqual(formatted, "2024-10-22T14:30:00Z")

    def test_fmt_rfc3339_naive_datetime(self):
        """Test formatting naive datetime (adds user's timezone then converts to UTC)."""
        dt = datetime(2024, 10, 22, 14, 30, 0)
        formatted = self.toolkit._fmt_rfc3339(dt)
        self.assertIn("2024-10-22T14:30:00", formatted)
        self.assertTrue(formatted.endswith("Z"))

    def test_first_not_none_multiple_values(self):
        """Test returning first non-None value."""
        result = _first_not_none(None, None, "value3", "value4")
        self.assertEqual(result, "value3")

    def test_first_not_none_all_none(self):
        """Test when all values are None."""
        result = _first_not_none(None, None, None)
        self.assertIsNone(result)

    def test_first_not_none_first_value(self):
        """Test returning first value when it's not None."""
        result = _first_not_none("first", "second", "third")
        self.assertEqual(result, "first")

    def test_normalize_event_kwargs_defaults(self):
        """Test normalizing event kwargs with defaults."""
        result = _normalize_event_kwargs()
        self.assertEqual(result["summary"], "Untitled Meeting")
        self.assertIsNone(result["timezone_str"])  # Now returns None instead of hardcoded "Asia/Jerusalem"
        self.assertEqual(result["attendees"], [])
        self.assertIsNone(result["start"])

    def test_normalize_event_kwargs_summary_vs_title(self):
        """Test that summary takes precedence over title."""
        result = _normalize_event_kwargs(summary="My Meeting", title="Old Title")
        self.assertEqual(result["summary"], "My Meeting")

    def test_normalize_event_kwargs_title_fallback(self):
        """Test using title when summary is not provided."""
        result = _normalize_event_kwargs(title="Meeting Title")
        self.assertEqual(result["summary"], "Meeting Title")

    def test_normalize_event_kwargs_all_fields(self):
        """Test normalizing with all fields provided."""
        result = _normalize_event_kwargs(
            summary="Team Sync",
            start="2024-10-22T14:00:00Z",
            duration_minutes=60,
            attendees=["alice@example.com", "bob@example.com"],
            timezone_str="America/New_York",
            location="Conference Room A",
            description="Weekly team meeting",
            send_updates="all",
        )
        self.assertEqual(result["summary"], "Team Sync")
        self.assertEqual(result["start"], "2024-10-22T14:00:00Z")
        self.assertEqual(result["duration_minutes"], 60)
        self.assertEqual(len(result["attendees"]), 2)
        self.assertEqual(result["timezone_str"], "America/New_York")
        self.assertEqual(result["location"], "Conference Room A")
        self.assertEqual(result["description"], "Weekly team meeting")
        self.assertEqual(result["send_updates"], "all")


class TestContactsAuthError(unittest.TestCase):
    """Test suite for ContactsAuthError exception."""

    def test_exception_can_be_raised(self):
        """Test that ContactsAuthError can be raised and caught."""
        with self.assertRaises(ContactsAuthError) as context:
            raise ContactsAuthError("Authentication failed")

        self.assertIn("Authentication failed", str(context.exception))

    def test_exception_is_runtime_error(self):
        """Test that ContactsAuthError is a RuntimeError."""
        self.assertTrue(issubclass(ContactsAuthError, RuntimeError))


class TestCalendarToolkit(unittest.TestCase):
    """Test suite for CalendarToolkit class."""

    def test_init_with_auth(self):
        """Test toolkit initialization with authentication enabled."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.user_id, "user123")
        self.assertEqual(toolkit.organizer_email, "test@example.com")
        self.assertEqual(toolkit.service_name, "google_calendar")
        # When auth=True, toolkit provides schedule_meeting tool
        self.assertIn("schedule_meeting", [getattr(t, "__name__", None) for t in toolkit.tools])

    def test_init_without_auth(self):
        """Test toolkit initialization without authentication."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="calendar",
            auth=False,
            fetch_token_func=fetch_token,
        )

        # When auth=False, toolkit provides auth_required tool instead of schedule_meeting
        self.assertIn("calendar_auth_required", [getattr(t, "__name__", None) for t in toolkit.tools])
        self.assertNotIn("schedule_meeting", [getattr(t, "__name__", None) for t in toolkit.tools])

    def test_toolkit_is_agno_toolkit(self):
        """Test that CalendarToolkit is an Agno Toolkit."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertIsInstance(toolkit, Toolkit)

    def test_toolkit_has_required_attributes(self):
        """Test that toolkit has required attributes."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        # Check toolkit has essential attributes
        self.assertTrue(hasattr(toolkit, "user_id"))
        self.assertTrue(hasattr(toolkit, "organizer_email"))
        self.assertTrue(hasattr(toolkit, "service_name"))
        self.assertTrue(hasattr(toolkit, "context"))
        self.assertTrue(hasattr(toolkit, "_fetch_token_func"))

    def test_toolkit_service_name_google(self):
        """Test toolkit with Google Calendar service name."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "google_calendar")

    def test_toolkit_service_name_microsoft(self):
        """Test toolkit with Microsoft Calendar service name."""
        fetch_token = Mock(return_value="test_token")

        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="microsoft_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        self.assertEqual(toolkit.service_name, "microsoft_calendar")

    def test_parse_attendees_from_strings_name_and_email(self):
        """Test parsing 'name email' format."""
        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        result = toolkit._parse_attendees_from_strings(["Alice alice@example.com", "Bob bob@example.com"])

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].name, "Alice")
        self.assertEqual(result[0].email, "alice@example.com")
        self.assertEqual(result[1].name, "Bob")
        self.assertEqual(result[1].email, "bob@example.com")

    def test_parse_attendees_from_strings_email_only(self):
        """Test parsing email-only format."""
        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        result = toolkit._parse_attendees_from_strings(["alice@example.com", "bob@example.com"])

        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0].name)
        self.assertEqual(result[0].email, "alice@example.com")
        self.assertIsNone(result[1].name)
        self.assertEqual(result[1].email, "bob@example.com")

    def test_parse_attendees_from_strings_empty_list(self):
        """Test parsing empty attendee list."""
        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        result = toolkit._parse_attendees_from_strings([])
        self.assertEqual(len(result), 0)

        result = toolkit._parse_attendees_from_strings(None)
        self.assertEqual(len(result), 0)

    def test_ensure_organizer_in_attendees_adds_organizer(self):
        """Test that organizer is added if missing."""
        from workspace_suite.models import Attendee

        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="organizer@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        attendees = [Attendee(name="Alice", email="alice@example.com"), Attendee(name="Bob", email="bob@example.com")]

        result = toolkit._ensure_organizer_in_attendees(attendees)

        self.assertEqual(len(result), 3)
        self.assertEqual(result[2].name, "Organizer")
        self.assertEqual(result[2].email, "organizer@example.com")

    def test_ensure_organizer_in_attendees_skips_if_present(self):
        """Test that organizer is not duplicated."""
        from workspace_suite.models import Attendee

        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="organizer@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        attendees = [
            Attendee(name="Alice", email="alice@example.com"),
            Attendee(name="Organizer", email="organizer@example.com"),
        ]

        result = toolkit._ensure_organizer_in_attendees(attendees)

        self.assertEqual(len(result), 2)  # Still 2, not 3

    def test_ensure_organizer_case_insensitive(self):
        """Test that organizer matching is case-insensitive."""
        from workspace_suite.models import Attendee

        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="ORGANIZER@EXAMPLE.COM",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        attendees = [
            Attendee(name="Organizer", email="organizer@example.com")  # lowercase
        ]

        result = toolkit._ensure_organizer_in_attendees(attendees)

        self.assertEqual(len(result), 1)  # Not duplicated despite case difference

    def test_event_result_to_dict_success(self):
        """Test EventResult to dict conversion for success."""
        from datetime import datetime, timezone

        from workspace_suite.models import Attendee, EventResult

        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        event_result = EventResult(
            status="success",
            event_id="event123",
            html_link="https://calendar.google.com/event123",
            conference_link="https://meet.google.com/abc-defg-hij",
            summary="Test Meeting",
            start=datetime(2024, 10, 22, 14, 0, 0, tzinfo=timezone.utc),
            end=datetime(2024, 10, 22, 15, 0, 0, tzinfo=timezone.utc),
            attendees=[Attendee(name="Alice", email="alice@example.com")],
            location="Conference Room",
            timezone="Asia/Jerusalem",
        )

        result = toolkit._event_result_to_dict(event_result)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["event_id"], "event123")
        self.assertEqual(result["html_link"], "https://calendar.google.com/event123")
        self.assertEqual(result["conference_link"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(result["summary"], "Test Meeting")
        self.assertEqual(result["start"], "2024-10-22T14:00:00Z")
        self.assertEqual(result["end"], "2024-10-22T15:00:00Z")
        self.assertEqual(len(result["attendees"]), 1)
        self.assertEqual(result["attendees"][0]["email"], "alice@example.com")
        self.assertEqual(result["location"], "Conference Room")
        self.assertEqual(result["timezone"], "Asia/Jerusalem")

    def test_event_result_to_dict_error(self):
        """Test EventResult to dict conversion for error."""
        from datetime import datetime, timezone

        from workspace_suite.models import Attendee, EventResult

        fetch_token = Mock(return_value="test_token")
        toolkit = CalendarToolkit(
            user_id="user123",
            organizer_email="test@example.com",
            service_name="google_calendar",
            auth=True,
            fetch_token_func=fetch_token,
        )

        event_result = EventResult(
            status="error",
            error={"message": "Calendar API error", "code": 403},
            summary="Test Meeting",
            start=datetime(2024, 10, 22, 14, 0, 0, tzinfo=timezone.utc),
            end=datetime(2024, 10, 22, 15, 0, 0, tzinfo=timezone.utc),
            attendees=[Attendee(name="Alice", email="alice@example.com")],
            location="Conference Room",
            timezone="Asia/Jerusalem",
        )

        result = toolkit._event_result_to_dict(event_result)

        self.assertEqual(result["status"], "error")
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], 403)
        self.assertEqual(result["summary"], "Test Meeting")


if __name__ == "__main__":
    unittest.main()
