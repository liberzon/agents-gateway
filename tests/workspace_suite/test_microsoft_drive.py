import os
import tempfile
import unittest

import httpx

from tests.workspace_suite.helpers import make_mock_client
from workspace_suite.config import ProviderConfig
from workspace_suite.providers.microsoft_drive import MicrosoftDriveProvider


class TestMicrosoftDriveProvider(unittest.TestCase):
    def test_upload_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"id": "od1", "name": "demo.txt", "webUrl": "https://onedrive.live.com/?id=od1"}
            )

        http_client = make_mock_client(handler)
        provider = MicrosoftDriveProvider(ProviderConfig(), http=http_client)

        with tempfile.NamedTemporaryFile("w+b", delete=False) as tf:
            tf.write(b"hello")
            tf.flush()
            path = tf.name
        try:
            res = provider.upload_file(token="t", path=path, name="demo.txt")
            self.assertEqual(res.status, "success")
            self.assertEqual(res.id, "od1")
        finally:
            try:
                os.remove(path)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
