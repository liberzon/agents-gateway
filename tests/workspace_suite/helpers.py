import httpx


def make_mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)
