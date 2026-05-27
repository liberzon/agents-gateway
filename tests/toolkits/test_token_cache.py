import time
import unittest
from threading import Thread
from unittest.mock import Mock

from toolkits.token_cache import TokenCache


class TestTokenCache(unittest.TestCase):
    """Test suite for TokenCache class."""

    def setUp(self):
        """Create a fresh cache instance for each test."""
        self.cache = TokenCache(ttl_seconds=1.0, cooldown_seconds=0.5)

    def test_init(self):
        """Test cache initialization."""
        cache = TokenCache(ttl_seconds=300.0, cooldown_seconds=5.0)
        self.assertEqual(cache._ttl, 300.0)
        self.assertEqual(cache._cooldown, 5.0)
        self.assertEqual(len(cache._cache), 0)

    def test_get_token_fresh_fetch(self):
        """Test fetching a new token when cache is empty."""
        fetcher = Mock(return_value="fresh_token_123")

        token = self.cache.get_token(service_name="google_calendar", user_id="user123", fetcher=fetcher, force=False)

        self.assertEqual(token, "fresh_token_123")
        fetcher.assert_called_once()

    def test_get_token_from_cache(self):
        """Test returning cached token within TTL."""
        fetcher = Mock(return_value="cached_token_456")

        # First call - fetch and cache
        token1 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token1, "cached_token_456")
        self.assertEqual(fetcher.call_count, 1)

        # Second call - should return cached token without fetching
        token2 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token2, "cached_token_456")
        self.assertEqual(fetcher.call_count, 1)  # Still only called once

    def test_get_token_ttl_expiration(self):
        """Test token expiration after TTL."""
        fetcher = Mock(side_effect=["token1", "token2"])

        # First fetch
        token1 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token1, "token1")

        # Wait for TTL to expire
        time.sleep(1.1)

        # Second fetch - should get new token
        token2 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token2, "token2")
        self.assertEqual(fetcher.call_count, 2)

    def test_get_token_force_refresh(self):
        """Test forcing a token refresh."""
        fetcher = Mock(side_effect=["token1", "token2"])

        # First fetch
        token1 = self.cache.get_token("google_calendar", "user123", fetcher, force=False)
        self.assertEqual(token1, "token1")

        # Force refresh
        token2 = self.cache.get_token("google_calendar", "user123", fetcher, force=True)
        self.assertEqual(token2, "token2")
        self.assertEqual(fetcher.call_count, 2)

    def test_get_token_multi_service_isolation(self):
        """Test that different services have isolated tokens."""
        fetcher1 = Mock(return_value="google_token")
        fetcher2 = Mock(return_value="microsoft_token")

        token1 = self.cache.get_token("google_calendar", "user123", fetcher1)
        token2 = self.cache.get_token("microsoft_calendar", "user123", fetcher2)

        self.assertEqual(token1, "google_token")
        self.assertEqual(token2, "microsoft_token")
        fetcher1.assert_called_once()
        fetcher2.assert_called_once()

    def test_get_token_multi_user_isolation(self):
        """Test that different users have isolated tokens."""
        fetcher1 = Mock(return_value="user1_token")
        fetcher2 = Mock(return_value="user2_token")

        token1 = self.cache.get_token("google_calendar", "user1", fetcher1)
        token2 = self.cache.get_token("google_calendar", "user2", fetcher2)

        self.assertEqual(token1, "user1_token")
        self.assertEqual(token2, "user2_token")
        fetcher1.assert_called_once()
        fetcher2.assert_called_once()

    def test_get_token_error_handling(self):
        """Test error handling during token fetch."""
        fetcher = Mock(side_effect=Exception("Network error"))

        token = self.cache.get_token("google_calendar", "user123", fetcher)

        self.assertIsNone(token)
        fetcher.assert_called_once()

    def test_get_token_error_cooldown(self):
        """Test cooldown period after error."""
        call_count = [0]

        def failing_fetcher():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First call fails")
            return "success_token"

        # First call - fails
        token1 = self.cache.get_token("google_calendar", "user123", failing_fetcher)
        self.assertIsNone(token1)

        # Second call - within cooldown, should not retry
        token2 = self.cache.get_token("google_calendar", "user123", failing_fetcher)
        self.assertIsNone(token2)
        self.assertEqual(call_count[0], 1)  # Only called once due to cooldown

        # Wait for cooldown to expire
        time.sleep(0.6)

        # Third call - after cooldown, should retry and succeed
        token3 = self.cache.get_token("google_calendar", "user123", failing_fetcher)
        self.assertEqual(token3, "success_token")
        self.assertEqual(call_count[0], 2)

    def test_invalidate_token(self):
        """Test invalidating a cached token."""
        fetcher = Mock(side_effect=["token1", "token2"])

        # Cache a token
        token1 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token1, "token1")

        # Invalidate it
        self.cache.invalidate("google_calendar", "user123")

        # Next fetch should get new token
        token2 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertEqual(token2, "token2")
        self.assertEqual(fetcher.call_count, 2)

    def test_invalidate_nonexistent_token(self):
        """Test invalidating a token that doesn't exist."""
        # Should not raise an error
        self.cache.invalidate("google_calendar", "user123")

    def test_clear_cache(self):
        """Test clearing all cached tokens."""
        fetcher = Mock(side_effect=["token1", "token2", "token3"])

        # Cache multiple tokens
        self.cache.get_token("google_calendar", "user1", fetcher)
        self.cache.get_token("microsoft_calendar", "user1", fetcher)
        self.cache.get_token("google_calendar", "user2", fetcher)

        # Verify cache has 3 entries
        stats = self.cache.get_cache_stats()
        self.assertEqual(stats["total_entries"], 3)

        # Clear cache
        self.cache.clear()

        # Verify cache is empty
        stats = self.cache.get_cache_stats()
        self.assertEqual(stats["total_entries"], 0)

    def test_get_cache_stats_empty(self):
        """Test cache statistics when empty."""
        stats = self.cache.get_cache_stats()

        self.assertEqual(stats["total_entries"], 0)
        self.assertEqual(stats["valid_tokens"], 0)
        self.assertEqual(stats["expired_tokens"], 0)
        self.assertEqual(stats["errored_tokens"], 0)

    def test_get_cache_stats_with_tokens(self):
        """Test cache statistics with various token states."""
        # Add valid token
        fetcher1 = Mock(return_value="valid_token")
        self.cache.get_token("google_calendar", "user1", fetcher1)

        # Add token that will expire
        fetcher2 = Mock(return_value="expiring_token")
        self.cache.get_token("microsoft_calendar", "user2", fetcher2)
        time.sleep(1.1)  # Wait for TTL expiration - this will expire both tokens!

        # Add token with error (after sleep, so first token is also expired now)
        fetcher3 = Mock(side_effect=Exception("Error"))
        self.cache.get_token("google_drive", "user3", fetcher3)

        stats = self.cache.get_cache_stats()

        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["valid_tokens"], 2)  # First two are valid (third errored)
        self.assertEqual(stats["expired_tokens"], 2)  # First two are expired (>1.1s old)
        self.assertEqual(stats["errored_tokens"], 1)  # Third one errored

    def test_thread_safety(self):
        """Test thread-safe concurrent access."""
        call_count = [0]

        def slow_fetcher():
            call_count[0] += 1
            time.sleep(0.1)
            return f"token_{call_count[0]}"

        results = []

        def fetch_token():
            token = self.cache.get_token("google_calendar", "user123", slow_fetcher)
            results.append(token)

        # Start multiple threads trying to fetch the same token
        threads = [Thread(target=fetch_token) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same token (first one fetched)
        self.assertEqual(len(set(results)), 1)
        # Fetcher should only be called once due to locking
        self.assertEqual(call_count[0], 1)

    def test_token_returned_as_none_during_error_cooldown_with_no_previous_token(self):
        """Test that None is returned during cooldown when no previous token exists."""
        fetcher = Mock(side_effect=Exception("Network error"))

        # First call fails, no previous token
        token1 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertIsNone(token1)

        # Second call within cooldown, should still return None
        token2 = self.cache.get_token("google_calendar", "user123", fetcher)
        self.assertIsNone(token2)
        self.assertEqual(fetcher.call_count, 1)  # Only called once due to cooldown


if __name__ == "__main__":
    unittest.main()
