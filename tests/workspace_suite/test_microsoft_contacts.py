import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.models import Contact
from workspace_suite.providers.microsoft_contacts import MicrosoftContactsProvider


class TestMicrosoftContactsProvider(unittest.TestCase):
    def test_create_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "c_ms_1", "@odata.etag": 'W/"123"'})

        http_client = make_mock_client(handler)
        provider = MicrosoftContactsProvider(ProviderConfig(), http=http_client)
        c = Contact(given_name="Alex", emails=["alex@example.com"])
        res = provider.create_contact(token="t", contact=c)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.resource_name, "c_ms_1")


if __name__ == "__main__":
    unittest.main()
