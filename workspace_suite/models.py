from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Sequence


# Calendar
@dataclass(frozen=True)
class Attendee:
    name: Optional[str]
    email: str
    role: Literal["required", "optional"] = "required"


@dataclass(frozen=True)
class EventCreateRequest:
    summary: str
    start: datetime
    end: datetime
    description: Optional[str] = None
    attendees: Sequence[Attendee] = ()
    location: Optional[str] = None
    timezone: Optional[str] = None
    conference: bool = False
    send_updates: Literal["all", "externalOnly", "none"] = "all"


@dataclass(frozen=True)
class EventResult:
    status: Literal["success", "error"]
    event_id: Optional[str] = None
    html_link: Optional[str] = None
    conference_link: Optional[str] = None
    summary: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    timezone: Optional[str] = None
    attendees: Sequence[Attendee] = ()
    location: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


# Mail
@dataclass(frozen=True)
class EmailMessage:
    to: Sequence[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    cc: Sequence[str] = ()
    bcc: Sequence[str] = ()
    attachments: Sequence[str] = ()
    thread_id: Optional[str] = None


@dataclass(frozen=True)
class EmailResult:
    status: Literal["success", "error"]
    id: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


# Drive
@dataclass(frozen=True)
class DriveFileResult:
    status: Literal["success", "error"]
    id: Optional[str] = None
    name: Optional[str] = None
    web_view_link: Optional[str] = None
    mime_type: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    size: Optional[str] = None
    owners: Optional[Sequence[str]] = None
    error: Optional[Dict[str, Any]] = None


# Contacts
@dataclass(frozen=True)
class Contact:
    given_name: str
    family_name: Optional[str] = None
    emails: Sequence[str] = ()
    phones: Sequence[str] = ()
    company: Optional[str] = None
    job_title: Optional[str] = None


@dataclass(frozen=True)
class ContactResult:
    status: Literal["success", "error"]
    resource_name: Optional[str] = None
    etag: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


# Free/Busy
@dataclass(frozen=True)
class TimePeriod:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class BusySlot:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class FreeBusyRequest:
    calendars: Sequence[str]
    time_min: datetime
    time_max: datetime
    timezone: Optional[str] = None
    interval_minutes: int = 30


@dataclass(frozen=True)
class FreeBusyCalendar:
    calendar: str
    busy: Sequence[BusySlot] = ()


@dataclass(frozen=True)
class FreeBusyResult:
    status: Literal["success", "error"]
    calendars: Sequence[FreeBusyCalendar] = ()
    error: Optional[Dict[str, Any]] = None
