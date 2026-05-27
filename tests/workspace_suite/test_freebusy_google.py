import unittest
from datetime import datetime, timedelta

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import FreeBusyRequest
from workspace_suite.providers.google_freebusy import GoogleFreeBusyProvider


class TestGoogleFreeBusy(unittest.TestCase):
    def test_freebusy_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "calendars": {
                        "alex@example.com": {"busy": [{"start": "2025-10-21T07:00:00Z", "end": "2025-10-21T08:00:00Z"}]}
                    }
                },
            )

        http_client = make_mock_client(handler)
        provider = GoogleFreeBusyProvider(ProviderConfig(), http=http_client)
        now = datetime.fromisoformat("2025-10-21T06:00:00+00:00")
        req = FreeBusyRequest(
            calendars=["alex@example.com"], time_min=now, time_max=now + timedelta(hours=4), timezone="UTC"
        )
        res = provider.query_freebusy(token="t", req=req)
        self.assertEqual(res.status, "success")
        self.assertEqual(len(res.calendars), 1)
        self.assertEqual(len(res.calendars[0].busy), 1)


if __name__ == "__main__":
    unittest.main()
