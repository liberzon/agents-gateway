import json
import unittest
from datetime import datetime, timedelta

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import Attendee, EventCreateRequest
from workspace_suite.providers.google_calendar import GoogleCalendarProvider


class TestGoogleCalendarProvider(unittest.TestCase):
    def test_create_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.host, "www.googleapis.com")
            body = json.loads(request.content.decode())
            self.assertEqual(body["summary"], "Team Sync")
            return httpx.Response(
                200,
                json={
                    "id": "evt_1",
                    "htmlLink": "https://calendar.google.com/event?eid=evt_1",
                    "hangoutLink": "https://meet.google.com/abc",
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleCalendarProvider(ProviderConfig(default_timezone="Asia/Jerusalem"), http=http_client)

        start = datetime.fromisoformat("2025-10-21T10:00:00+03:00")
        end = start + timedelta(minutes=30)
        req = EventCreateRequest(
            summary="Team Sync",
            start=start,
            end=end,
            attendees=[Attendee(name="Alex", email="alex@example.com")],
            timezone="Asia/Jerusalem",
            conference=True,
        )
        res = provider.create_event(token="t", calendar_id="primary", req=req)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.event_id, "evt_1")
        self.assertIn("meet.google.com", res.conference_link or "")


if __name__ == "__main__":
    unittest.main()
