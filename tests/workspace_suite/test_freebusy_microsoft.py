import unittest
from datetime import datetime, timedelta

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import FreeBusyRequest
from workspace_suite.providers.microsoft_freebusy import MicrosoftFreeBusyProvider


class TestMicrosoftFreeBusy(unittest.TestCase):
    def test_get_schedule_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "scheduleId": "alex@example.com",
                            "scheduleItems": [
                                {
                                    "start": {"dateTime": "2025-10-21T09:00:00+00:00"},
                                    "end": {"dateTime": "2025-10-21T10:00:00+00:00"},
                                }
                            ],
                        }
                    ]
                },
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftFreeBusyProvider(ProviderConfig(), http=http_client)
        now = datetime.fromisoformat("2025-10-21T08:00:00+00:00")
        req = FreeBusyRequest(
            calendars=["alex@example.com"], time_min=now, time_max=now + timedelta(hours=4), timezone="UTC"
        )
        res = provider.query_freebusy(token="t", req=req)
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.calendars), 1)
        self.assertEqual(len(res.calendars[0].busy), 1)


if __name__ == "__main__":
    unittest.main()
