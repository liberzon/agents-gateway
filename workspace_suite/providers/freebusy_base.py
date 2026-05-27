from typing import Protocol, Tuple

from ..models import FreeBusyRequest, FreeBusyResult


class FreeBusyProvider(Protocol):
    def query_freebusy(
        self,
        token: str,
        req: FreeBusyRequest,
        http_timeout: float | Tuple[float, float] = 15.0,
        default_timezone: str = "UTC",
    ) -> FreeBusyResult: ...
