"""
Token Cache System for Toolkits

This module provides a thread-safe, shared token caching system for managing
OAuth access tokens across multiple services and users.

The TokenCache class handles:
- Token storage with TTL-based expiration
- Multi-service and multi-user isolation
- Automatic error handling with cooldown periods
- Thread-safe concurrent access

Usage Example
=============

    >>> from toolkits.token_cache import TokenCache, fetch_access_token
    >>>
    >>> # Create global cache instance
    >>> token_cache = TokenCache(ttl_seconds=300.0, cooldown_seconds=5.0)
    >>>
    >>> # Fetch token with automatic caching
    >>> token = token_cache.get_token(
    ...     service_name="google_calendar",
    ...     user_id="user123",
    ...     fetcher=lambda: fetch_access_token("user123", "google_calendar"),
    ...     force=False
    ... )
    >>>
    >>> # Invalidate specific token
    >>> token_cache.invalidate("google_calendar", "user123")
    >>>
    >>> # Clear all tokens
    >>> token_cache.clear()

Architecture
============

Tokens are keyed by (service_name, user_id) tuples, allowing:
- Multiple services per user (e.g., Google and Microsoft calendars)
- Multiple users per service (multi-tenant support)
- Isolated token storage without cross-contamination

Token Lifecycle:
1. Request token via get_token()
2. Check cache for fresh token (within TTL)
3. If stale/missing, call fetcher function
4. Cache new token with timestamp
5. On error, record error timestamp and enter cooldown
6. During cooldown, return cached token (even if stale)

Thread Safety
=============

All cache operations are protected by a threading.Lock to ensure:
- Safe concurrent access from multiple agent instances
- No race conditions during token fetch
- Atomic cache updates

Performance
===========

The cache minimizes backend token service calls by:
- Returning cached tokens within TTL window
- Implementing cooldown after errors
- Avoiding redundant fetches for same service/user

Security
========

- Tokens are stored in memory only (not persisted to disk)
- No tokens appear in logs
- Automatic expiration prevents stale token usage
- Individual token invalidation on auth errors
"""

import logging
import time
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TokenCache:
    """
    Thread-safe token cache for managing OAuth access tokens across multiple
    services and users.

    Tokens are keyed by (service_name, user_id) tuple.
    Supports TTL-based expiration and error cooldown.

    Attributes:
        _cache: Internal dictionary storing token data
        _lock: Threading lock for concurrent access protection
        _ttl: Time-to-live for cached tokens in seconds
        _cooldown: Cooldown period after errors in seconds
    """

    def __init__(self, ttl_seconds: float = 3300.0, cooldown_seconds: float = 5.0):
        """
        Initialize token cache.

        Args:
            ttl_seconds: Time-to-live for cached tokens (default: 55 minutes / 3300 seconds)
                        Set to 55 minutes to match OAuth2 token expiry (~1 hour) minus buffer
            cooldown_seconds: Cooldown period after errors before retrying (default: 5 seconds)
        """
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds
        self._cooldown = cooldown_seconds

    def _now(self) -> float:
        """Get current timestamp."""
        return time.time()

    def get_token(
        self, service_name: str, user_id: str, fetcher: Callable[[], str], force: bool = False
    ) -> Optional[str]:
        """
        Get a cached token or fetch a new one.

        This method checks the cache for a valid token. If found and fresh,
        it returns immediately. If stale or missing, it calls the fetcher
        function to obtain a new token.

        During cooldown periods (after errors), it returns the cached token
        even if stale, to avoid hammering the backend service.

        Args:
            service_name: Name of the service (e.g., "google_calendar", "microsoft_calendar")
            user_id: User identifier
            fetcher: Callable that fetches a new token (should return str)
            force: If True, bypass cache and fetch fresh token

        Returns:
            Access token string, or None if unavailable

        Examples:
            >>> def my_fetcher():
            ...     return fetch_access_token("user123", "google_calendar")
            >>>
            >>> token = cache.get_token(
            ...     service_name="google_calendar",
            ...     user_id="user123",
            ...     fetcher=my_fetcher,
            ...     force=False
            ... )
            >>> print(token)  # "ya29.a0AfH6SMB..."

        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        key = (service_name, user_id)
        now = self._now()

        with self._lock:
            cached = self._cache.get(key)

            # Return fresh cached token if available
            if not force and cached:
                token = cached.get("access_token")
                fetched_at = cached.get("fetched_at", 0.0)

                if token and (now - fetched_at < self._ttl):
                    return token

                # Check cooldown period after errors
                last_error_at = cached.get("last_error_at", 0.0)
                if last_error_at and (now - last_error_at < self._cooldown):
                    return token or None

            # Fetch new token
            try:
                token = fetcher()

                self._cache[key] = {
                    "access_token": token,
                    "fetched_at": now,
                    "valid": bool(token),
                    "last_error_at": 0.0,
                }

                return token

            except Exception as e:
                logger.warning(f"Token fetch failed for {service_name}/{user_id}: {e}")

                # Update error timestamp
                if cached:
                    cached["last_error_at"] = now
                    cached["valid"] = False
                else:
                    self._cache[key] = {
                        "access_token": None,
                        "fetched_at": 0.0,
                        "valid": False,
                        "last_error_at": now,
                    }

                return cached.get("access_token") if cached else None

    def invalidate(self, service_name: str, user_id: str) -> None:
        """
        Invalidate a cached token.

        This removes the token from the cache, forcing a fresh fetch
        on the next get_token() call.

        Args:
            service_name: Name of the service
            user_id: User identifier

        Examples:
            >>> cache.invalidate("google_calendar", "user123")
            >>> # Next get_token() will fetch fresh token

        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        key = (service_name, user_id)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.info(f"Invalidated token for {service_name}/{user_id}")

    def clear(self) -> None:
        """
        Clear all cached tokens.

        This removes all tokens from the cache. Use with caution as it
        will force fresh fetches for all services and users.

        Examples:
            >>> cache.clear()
            >>> # All subsequent get_token() calls will fetch fresh tokens

        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cached token(s)")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring and debugging.

        Returns:
            Dictionary with cache statistics:
            - total_entries: Number of cached tokens
            - valid_tokens: Number of tokens marked as valid
            - expired_tokens: Number of tokens past TTL
            - errored_tokens: Number of tokens with recent errors

        Examples:
            >>> stats = cache.get_cache_stats()
            >>> print(f"Total cached tokens: {stats['total_entries']}")
            >>> print(f"Valid tokens: {stats['valid_tokens']}")

        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            now = self._now()
            total = len(self._cache)
            valid = sum(1 for v in self._cache.values() if v.get("valid", False))
            expired = sum(
                1 for v in self._cache.values() if v.get("access_token") and (now - v.get("fetched_at", 0) >= self._ttl)
            )
            errored = sum(1 for v in self._cache.values() if v.get("last_error_at", 0) > 0)

            return {
                "total_entries": total,
                "valid_tokens": valid,
                "expired_tokens": expired,
                "errored_tokens": errored,
            }


__all__ = [
    "TokenCache",
]
