import datetime
import time
from dataclasses import dataclass
from typing import Optional


def get_system_timezone() -> str:
    """Return the system's local timezone as an IANA identifier (e.g., 'Asia/Jerusalem')."""
    # First try: Check if datetime.now().astimezone() gives us a ZoneInfo
    local_tz = datetime.datetime.now().astimezone().tzinfo
    if local_tz and hasattr(local_tz, "key"):
        return local_tz.key  # type: ignore[return-value]

    # Second try: Use time.tzname to get the system timezone
    # time.tzname gives us (standard_name, dst_name) like ('IST', 'IDT')
    # We need to map this to the IANA identifier
    try:
        # Get the local timezone name from the system
        if time.daylight:
            tz_name = time.tzname[time.daylight]
        else:
            tz_name = time.tzname[0]

        # Map common timezone abbreviations to IANA identifiers
        tz_abbrev_map = {
            "IST": "Asia/Jerusalem",  # Israel Standard Time
            "IDT": "Asia/Jerusalem",  # Israel Daylight Time
            "EST": "America/New_York",
            "EDT": "America/New_York",
            "PST": "America/Los_Angeles",
            "PDT": "America/Los_Angeles",
            "GMT": "UTC",
            "UTC": "UTC",
        }

        if tz_name in tz_abbrev_map:
            return tz_abbrev_map[tz_name]
    except Exception:
        pass

    # Last resort: return UTC
    return "UTC"


@dataclass
class ProviderConfig:
    http_timeout: float | tuple[float, float] = 15.0
    default_timezone: str = None  # type: ignore[assignment]
    base_url: Optional[str] = None

    def __post_init__(self):
        """Set default timezone to system timezone if not provided."""
        if self.default_timezone is None:
            self.default_timezone = get_system_timezone()
