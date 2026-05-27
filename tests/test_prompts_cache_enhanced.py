import asyncio
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import cache.prompts_cache as prompts_cache
from cache.prompts_cache import (
    extend_cache_ttl,
    get_cache_status,
    invalidate_prompt_cache,
    load_all_prompts_to_cache,
    prompt_cache,
    record_cache_hit,
    record_cache_miss,
    refresh_all_prompts,
    wait_for_cache_ready,
)


class TestPromptsCache(unittest.TestCase):
    def setUp(self):
        # Reset cache state before each test
        prompts_cache.is_cache_initialized = False
        prompts_cache.cache_initialization_time = None
        prompts_cache.last_full_refresh_time = None
        prompts_cache.cache_statistics = {
            "total_prompts_loaded": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "full_refreshes": 0,
            "partial_refreshes": 0,
            "load_errors": 0,
        }
        prompt_cache.clear()

    def test_cache_hit_miss_tracking(self):
        """Test that cache hits and misses are properly tracked."""
        # Test cache miss
        record_cache_miss("test_prompt")
        self.assertEqual(prompts_cache.cache_statistics["cache_misses"], 1)

        # Test cache hit
        record_cache_hit("test_prompt")
        self.assertEqual(prompts_cache.cache_statistics["cache_hits"], 1)

        # Test multiple hits/misses
        record_cache_hit("prompt1")
        record_cache_hit("prompt2")
        record_cache_miss("prompt3")

        self.assertEqual(prompts_cache.cache_statistics["cache_hits"], 3)
        self.assertEqual(prompts_cache.cache_statistics["cache_misses"], 2)

    def test_cache_ttl_extension(self):
        """Test that cache TTL extension works."""
        # Add item to cache
        prompt_cache["test_prompt"] = {"template": "test template"}

        # Extend TTL
        extend_cache_ttl("test_prompt")

        # Item should still be in cache
        self.assertIn("test_prompt", prompt_cache)

        # Test with non-existent item
        extend_cache_ttl("nonexistent_prompt")  # Should not raise error

    def test_cache_invalidation(self):
        """Test cache invalidation functionality."""
        # Add items to cache
        prompt_cache["prompt1"] = {"template": "template1"}
        prompt_cache["prompt2"] = {"template": "template2"}
        prompts_cache.is_cache_initialized = True

        # Test specific prompt invalidation
        invalidate_prompt_cache("prompt1")
        self.assertNotIn("prompt1", prompt_cache)
        self.assertIn("prompt2", prompt_cache)

        # Test full cache invalidation
        invalidate_prompt_cache()
        self.assertEqual(len(prompt_cache), 0)
        self.assertFalse(prompts_cache.is_cache_initialized)

    def test_get_cache_status(self):
        """Test cache status retrieval."""
        status = get_cache_status()

        # Check required fields
        self.assertIn("is_initialized", status)
        self.assertIn("cache_size", status)
        self.assertIn("cache_maxsize", status)
        self.assertIn("cache_ttl_seconds", status)
        self.assertIn("refresh_interval_seconds", status)
        self.assertIn("statistics", status)

        # Test with initialized cache
        prompts_cache.is_cache_initialized = True
        prompts_cache.cache_initialization_time = datetime.now()
        prompts_cache.last_full_refresh_time = datetime.now()

        status = get_cache_status()
        self.assertTrue(status["is_initialized"])
        self.assertIsNotNone(status["initialization_time"])
        self.assertIsNotNone(status["last_refresh_time"])
        self.assertIsNotNone(status["next_refresh_time"])

    def test_wait_for_cache_ready_success(self):
        """Test waiting for cache to be ready - success case."""

        async def make_cache_ready():
            await asyncio.sleep(0.1)
            prompts_cache.is_cache_initialized = True

        async def test_wait():
            # Start task to make cache ready
            asyncio.create_task(make_cache_ready())

            # Wait for cache
            ready = await wait_for_cache_ready(timeout_seconds=1)
            self.assertTrue(ready)

        asyncio.run(test_wait())

    def test_wait_for_cache_ready_timeout(self):
        """Test waiting for cache to be ready - timeout case."""

        async def test_wait():
            # Cache remains uninitialized
            ready = await wait_for_cache_ready(timeout_seconds=0.1)
            self.assertFalse(ready)

        asyncio.run(test_wait())

    def test_wait_for_cache_ready_already_ready(self):
        """Test waiting for cache when it's already ready."""
        prompts_cache.is_cache_initialized = True

        async def test_wait():
            ready = await wait_for_cache_ready(timeout_seconds=1)
            self.assertTrue(ready)

        asyncio.run(test_wait())

    @patch("prompts.storage.get_prompt_storage")
    def test_load_all_prompts_to_cache_success(self, mock_get_storage):
        """Test successful cache initialization."""
        # Create mock prompts
        mock_prompt1 = MagicMock()
        mock_prompt1.id = "prompt1"
        mock_prompt1.template = "template1"
        mock_prompt1.description = "desc1"
        mock_prompt1.tags = []
        mock_prompt1.tools = []

        mock_prompt2 = MagicMock()
        mock_prompt2.id = "prompt2"
        mock_prompt2.template = "template2"
        mock_prompt2.description = "desc2"
        mock_prompt2.tags = []
        mock_prompt2.tools = []

        # Mock storage backend
        mock_storage = MagicMock()
        mock_storage.get_all.return_value = [mock_prompt1, mock_prompt2]
        mock_get_storage.return_value = mock_storage

        async def test_load():
            await load_all_prompts_to_cache()

            # Check cache is marked as initialized
            self.assertTrue(prompts_cache.is_cache_initialized)
            self.assertIsNotNone(prompts_cache.cache_initialization_time)
            self.assertEqual(prompts_cache.cache_statistics["total_prompts_loaded"], 2)

            # Verify storage was called
            mock_storage.get_all.assert_called_once()

        asyncio.run(test_load())

    @patch("prompts.storage.get_prompt_storage")
    def test_load_all_prompts_to_cache_failure(self, mock_get_storage):
        """Test cache initialization failure (empty prompts)."""
        # Mock storage backend to return empty list (simulates no prompts)
        mock_storage = MagicMock()
        mock_storage.get_all.return_value = []
        mock_get_storage.return_value = mock_storage

        async def test_load():
            await load_all_prompts_to_cache()

            # Check cache is marked as initialized (even with empty prompts)
            # The new implementation marks as initialized even with empty results
            self.assertTrue(prompts_cache.is_cache_initialized)
            self.assertEqual(prompts_cache.cache_statistics["total_prompts_loaded"], 0)

        asyncio.run(test_load())

    @patch("prompts.storage.get_prompt_storage")
    def test_load_all_prompts_to_cache_exception(self, mock_get_storage):
        """Test cache initialization with exception."""
        # Mock storage backend to raise exception
        mock_get_storage.side_effect = Exception("Test error")

        async def test_load():
            await load_all_prompts_to_cache()

            # Check cache is still marked as initialized (to avoid blocking)
            # The new implementation marks as initialized even on error
            self.assertTrue(prompts_cache.is_cache_initialized)
            self.assertEqual(prompts_cache.cache_statistics["load_errors"], 1)

        asyncio.run(test_load())

    @patch("prompts.storage.get_prompt_storage")
    def test_refresh_all_prompts_success(self, mock_get_storage):
        """Test successful cache refresh."""
        # Create mock prompts
        mock_prompt1 = MagicMock()
        mock_prompt1.id = "prompt1"
        mock_prompt1.template = "template1"
        mock_prompt1.description = "desc1"
        mock_prompt1.tags = []
        mock_prompt1.tools = []

        mock_prompt2 = MagicMock()
        mock_prompt2.id = "prompt2"
        mock_prompt2.template = "template2"
        mock_prompt2.description = "desc2"
        mock_prompt2.tags = []
        mock_prompt2.tools = []

        # Mock storage backend
        mock_storage = MagicMock()
        mock_storage.get_all.return_value = [mock_prompt1, mock_prompt2]
        mock_get_storage.return_value = mock_storage

        async def test_refresh():
            await refresh_all_prompts()

            # Check refresh is recorded
            self.assertIsNotNone(prompts_cache.last_full_refresh_time)
            self.assertEqual(prompts_cache.cache_statistics["full_refreshes"], 1)
            self.assertEqual(prompts_cache.cache_statistics["total_prompts_loaded"], 2)

            # Verify storage was called
            mock_storage.get_all.assert_called_once()

        asyncio.run(test_refresh())

    @patch("prompts.storage.get_prompt_storage")
    def test_refresh_all_prompts_failure(self, mock_get_storage):
        """Test cache refresh failure (empty prompts)."""
        # Mock storage backend to return empty list
        mock_storage = MagicMock()
        mock_storage.get_all.return_value = []
        mock_get_storage.return_value = mock_storage

        async def test_refresh():
            await refresh_all_prompts()

            # Check refresh is recorded (even with empty prompts, refresh completes)
            self.assertIsNotNone(prompts_cache.last_full_refresh_time)
            self.assertEqual(prompts_cache.cache_statistics["full_refreshes"], 1)
            self.assertEqual(prompts_cache.cache_statistics["total_prompts_loaded"], 0)

        asyncio.run(test_refresh())

    @patch("prompts.storage.get_prompt_storage")
    def test_refresh_all_prompts_exception(self, mock_get_storage):
        """Test cache refresh with exception."""
        # Mock storage backend to raise exception
        mock_get_storage.side_effect = Exception("Test error")

        async def test_refresh():
            await refresh_all_prompts()

            # Check error is recorded
            self.assertEqual(prompts_cache.cache_statistics["load_errors"], 1)
            self.assertEqual(prompts_cache.cache_statistics["full_refreshes"], 0)

        asyncio.run(test_refresh())

    def test_cache_statistics_tracking(self):
        """Test that cache statistics are properly tracked."""
        initial_stats = prompts_cache.cache_statistics.copy()

        # Test various operations
        record_cache_hit("prompt1")
        record_cache_miss("prompt2")

        # Manually increment some stats to test
        prompts_cache.cache_statistics["full_refreshes"] += 1
        prompts_cache.cache_statistics["load_errors"] += 1

        # Check stats were updated
        self.assertEqual(prompts_cache.cache_statistics["cache_hits"], initial_stats["cache_hits"] + 1)
        self.assertEqual(prompts_cache.cache_statistics["cache_misses"], initial_stats["cache_misses"] + 1)
        self.assertEqual(prompts_cache.cache_statistics["full_refreshes"], initial_stats["full_refreshes"] + 1)
        self.assertEqual(prompts_cache.cache_statistics["load_errors"], initial_stats["load_errors"] + 1)

    def test_cache_size_tracking(self):
        """Test that cache size is properly tracked in status."""
        # Initially empty
        status = get_cache_status()
        self.assertEqual(status["cache_size"], 0)

        # Add items
        prompt_cache["prompt1"] = {"template": "template1"}
        prompt_cache["prompt2"] = {"template": "template2"}

        status = get_cache_status()
        self.assertEqual(status["cache_size"], 2)

        # Clear cache
        prompt_cache.clear()

        status = get_cache_status()
        self.assertEqual(status["cache_size"], 0)


if __name__ == "__main__":
    unittest.main()
