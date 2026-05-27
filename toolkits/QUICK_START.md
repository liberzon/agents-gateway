# Toolkits Package - Quick Start Guide

## What's in the Package?

```
toolkits/
├── __init__.py              # Package exports
├── token_cache.py           # Shared token caching
├── calendar.py              # Calendar toolkit (Google, Microsoft)
├── contacts.py              # Contacts toolkit (Google, Microsoft)
├── email.py                 # Email toolkit (Gmail, Outlook)
├── drive.py                 # Drive toolkit (Google Drive, OneDrive)
├── README.md                # Full documentation
├── API_REFERENCE.md         # Method specifications
├── CHANGELOG.md             # Version history
└── QUICK_START.md           # This file
```

## Overview

This package provides:
1. **TokenCache**: Thread-safe OAuth token management
2. **Toolkits**: AI agent integrations for workspace services
3. **Multi-Provider**: Support for Google and Microsoft services

## Basic Usage

### 1. Token Caching

```python
from toolkits.token_cache import TokenCache

# Create cache
cache = TokenCache(ttl_seconds=300.0)

# Get token (auto-fetches and caches)
token = cache.get_token(
    service_name="google_calendar",
    user_id="user123",
    fetcher=lambda: fetch_from_backend(),
    force=False  # Use cache if fresh
)
```

### 2. Using Toolkits

```python
from toolkits import CalendarToolkit, EmailToolkit, ContactsToolkit, DriveToolkit

# Calendar
calendar = CalendarToolkit(
    user_id="user123",
    organizer_email="user@example.com",
    service_name="google_calendar",
    auth=True,
    fetch_token_func=fetch_access_token
)

# Email
email = EmailToolkit(
    user_id="user123",
    service_name="gmail",
    auth=True,
    fetch_token_func=fetch_access_token
)

# Use with Agno agent
from agno.agent import Agent

agent = Agent(tools=[calendar, email])
```

## Available Toolkits

| Toolkit | Providers | Status |
|---------|-----------|--------|
| CalendarToolkit | Google Calendar, Microsoft Calendar | Complete |
| EmailToolkit | Gmail, Microsoft Outlook | Complete |
| ContactsToolkit | Google Contacts, Microsoft Contacts | Complete |
| DriveToolkit | Google Drive, Microsoft OneDrive | Complete |
| TokenCache | N/A | Complete |

## Quick Commands

```bash
# Test imports
python -c "from toolkits import CalendarToolkit; print('OK')"

# View structure
ls -lh toolkits/

# Read documentation
cat toolkits/README.md
cat toolkits/API_REFERENCE.md
```

## Documentation Files

- **README.md**: Complete package documentation
- **API_REFERENCE.md**: Method input/output specifications
- **CHANGELOG.md**: Version history and changes
- **QUICK_START.md**: This file

---

**Last Updated**: 2026-01-19
**Version**: 2.0.0
