import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import EmailMessage
from workspace_suite.providers.microsoft_mail import MicrosoftMailProvider


class TestMicrosoftMailProvider(unittest.TestCase):
    def test_send_accepted(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(202)

        http_client = make_mock_client(handler)
        provider = MicrosoftMailProvider(ProviderConfig(), http=http_client)
        msg = EmailMessage(to=["a@ex.com"], subject="Hello", body_text="Hi")
        res = provider.send_email(token="t", msg=msg)
        self.assertEqual(res.status, "success")


if __name__ == "__main__":
    unittest.main()
