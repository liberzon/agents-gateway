"""
Access Token Management

Provides utilities for fetching and checking user access tokens for various integrations.
"""

import asyncio
import concurrent.futures
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from api.services.token_refresh import get_user_tokens_for_agent
from db.session import get_db


@contextmanager
def db_session():
    """Context manager for database sessions."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()


async def fetch_tokens_internal(user_id: str, integration_key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Internal async function to fetch tokens with auto-refresh.

    Args:
        user_id: User identifier
        integration_key: Integration/service identifier

    Returns:
        Tuple of (token_data, error_message)
    """
    with db_session() as db:
        return await get_user_tokens_for_agent(db, user_id, integration_key)


def _await(coro_or_func):
    """
    Run an async coroutine from sync context, handling the case where an event loop is already running.

    This helper properly handles three cases:
    1. No event loop exists: Create new loop and run coroutine
    2. Event loop exists but not running: Use existing loop
    3. Event loop is already running: Run coroutine in separate thread to avoid "event loop already running" error

    Args:
        coro_or_func: Either an async coroutine object or a callable that returns a coroutine

    Returns:
        Result from the coroutine
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    # If no loop or loop not running, we can use standard approaches
    if not loop or not loop.is_running():
        # Get or create the coroutine
        if callable(coro_or_func):
            coro = coro_or_func()
        else:
            coro = coro_or_func

        if not loop:
            # No event loop exists - use asyncio.run()
            return asyncio.run(coro)
        else:
            # Event loop exists but not running
            return loop.run_until_complete(coro)

    # Event loop is already running - need to run in separate thread
    def run_in_thread():
        # Get or create the coroutine fresh in this thread
        if callable(coro_or_func):
            coro = coro_or_func()
        else:
            coro = coro_or_func

        # Use asyncio.run() which creates a new loop and properly cleans up
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()


def has_access_token(user_id: str, integration_key: str) -> bool:
    """
    Fast check if user has a token without triggering refresh.

    This function performs a lightweight database query to check token existence
    without fetching, decrypting, or refreshing the token.

    Use this for authentication flow decisions (which toolkit to show).
    Use fetch_access_token() when you actually need the token data.

    Args:
        user_id: User identifier
        integration_key: Integration/service identifier (e.g., "google_calendar")

    Returns:
        True if token exists in database (regardless of validity/expiration)
        False if no token found
    """
    try:
        from db.user_token_crud import has_user_token

        # Get database session (synchronous)
        db_gen = get_db()
        db = next(db_gen)

        try:
            return has_user_token(db, user_id, integration_key)
        finally:
            # Close the database session
            try:
                db_gen.close()
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Token existence check failed for {integration_key}: {e}")
        return False


def has_access_tokens_batch(user_id: str, integration_keys: List[str]) -> Dict[str, bool]:
    """
    Fast batch check if user has tokens for multiple integrations.

    This performs a SINGLE database query to check ALL integration keys at once,
    avoiding the overhead of multiple database sessions (much faster than calling
    has_access_token() multiple times).

    Args:
        user_id: User identifier
        integration_keys: List of integration keys to check (e.g., ["google_calendar", "google_gmail"])

    Returns:
        Dictionary mapping integration_key to boolean (exists or not)

    Performance:
        Single database session + single SQL query with IN clause.
        Example: 4 services checked in ~10ms vs ~3000ms for 4 individual checks.

    Example:
        >>> has_access_tokens_batch("user123", ["google_calendar", "google_gmail"])
        {"google_calendar": True, "google_gmail": False}
    """
    try:
        from db.user_token_crud import has_user_tokens_batch

        # Get database session (synchronous)
        db_gen = get_db()
        db = next(db_gen)

        try:
            return has_user_tokens_batch(db, user_id, integration_keys)
        finally:
            # Close the database session
            try:
                db_gen.close()
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Batch token existence check failed: {e}")
        # Return all False on error
        return {key: False for key in integration_keys}


def fetch_access_token(user_id: str, integration_key: str) -> str:
    """
    Fetch an access token for a user and integration.

    Args:
        user_id: User identifier
        integration_key: Integration/service identifier (e.g., "google_calendar")

    Returns:
        Access token string

    Raises:
        HTTPException: If token fetch fails
    """
    logging.info(f"Fetching access token for user_id={user_id}, integration_key={integration_key}")

    # Pass a lambda to _await() so the coroutine is created in the target thread's context
    token_data, err = _await(lambda: fetch_tokens_internal(user_id, integration_key))

    if err:
        logging.error(f"Failed to fetch token for user_id={user_id}, integration_key={integration_key}: {err}")
        raise HTTPException(status_code=401, detail=f"Failed to get token: {err}")

    logging.info(f"Successfully retrieved token for user_id={user_id}, integration_key={integration_key}")
    return (token_data or {}).get("access_token", "")
