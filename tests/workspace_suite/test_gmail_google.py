import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import EmailMessage
from workspace_suite.providers.google_gmail import GoogleGmailProvider


class TestGoogleGmailProvider(unittest.TestCase):
    def test_send_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "msg123", "threadId": "thr1"})

        http_client = make_mock_client(handler)
        provider = GoogleGmailProvider(ProviderConfig(), http=http_client)

        msg = EmailMessage(to=["a@example.com"], subject="Hi", body_text="Hello")
        res = provider.send_email(token="t", msg=msg)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.id, "msg123")


if __name__ == "__main__":
    unittest.main()
