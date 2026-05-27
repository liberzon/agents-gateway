import unittest
from datetime import datetime, timedelta

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import EventCreateRequest
from workspace_suite.providers.microsoft_calendar import MicrosoftCalendarProvider


class TestMicrosoftCalendarProvider(unittest.TestCase):
    def test_create_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "evt_ms_1",
                    "webLink": "https://outlook.office.com/calendar/item/evt_ms_1",
                    "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/xyz"},
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftCalendarProvider(ProviderConfig(), http=http_client)

        start = datetime.fromisoformat("2025-10-21T10:00:00+03:00")
        req = EventCreateRequest(
            summary="Sync", start=start, end=start + timedelta(minutes=30), timezone="Asia/Jerusalem", conference=True
        )
        res = provider.create_event(token="t", calendar_id="primary", req=req)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.event_id, "evt_ms_1")
        self.assertIn("teams.microsoft.com", res.conference_link or "")


if __name__ == "__main__":
    unittest.main()
