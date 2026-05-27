import unittest
from unittest.mock import AsyncMock, patch

from tests.test_utils import create_test_client


class TestAdminEndpoints(unittest.TestCase):
    def setUp(self):
        self.client, self.app = create_test_client()

    def test_get_cache_stats(self):
        """Test the cache stats endpoint."""
        response = self.client.get("/admin/cache/stats")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("prompt_cache", data)
        cache_info = data["prompt_cache"]
        self.assertIn("size", cache_info)
        self.assertIn("maxsize", cache_info)
        self.assertIn("ttl", cache_info)
        self.assertIn("currsize", cache_info)

    def test_invalidate_prompts_cache_all(self):
        """Test invalidating all prompts cache."""
        response = self.client.post("/admin/cache/invalidate/prompts")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("All prompt caches invalidated", data["message"])

    def test_invalidate_prompts_cache_specific(self):
        """Test invalidating specific prompt cache."""
        response = self.client.post("/admin/cache/invalidate/prompts?prompt_id=test_prompt")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("test_prompt", data["message"])

    @patch("api.routes.admin.get_cache_status")
    def test_get_cache_status_endpoint(self, mock_get_cache_status):
        """Test the cache status endpoint."""
        # Mock cache status
        mock_status = {
            "is_initialized": True,
            "cache_size": 10,
            "cache_maxsize": 1000,
            "statistics": {"cache_hits": 50, "cache_misses": 5},
        }
        mock_get_cache_status.return_value = mock_status

        response = self.client.get("/admin/cache/status")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data, mock_status)
        mock_get_cache_status.assert_called_once()

    @patch("api.routes.admin.get_cache_status")
    def test_get_cache_status_endpoint_error(self, mock_get_cache_status):
        """Test cache status endpoint error handling."""
        mock_get_cache_status.side_effect = Exception("Test error")

        response = self.client.get("/admin/cache/status")
        self.assertEqual(response.status_code, 500)

        data = response.json()
        self.assertIn("Failed to retrieve cache status", data["detail"])

    @patch("asyncio.create_task")
    @patch("api.routes.admin.load_all_prompts_to_cache")
    def test_reload_cache_endpoint(self, mock_load_prompts, mock_create_task):
        """Test the cache reload endpoint."""
        response = self.client.post("/admin/cache/reload")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Cache reload initiated", data["message"])
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("api.routes.admin.refresh_all_prompts")
    def test_refresh_cache_endpoint(self, mock_refresh_prompts, mock_create_task):
        """Test the cache refresh endpoint."""
        response = self.client.post("/admin/cache/refresh")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Cache refresh initiated", data["message"])
        mock_create_task.assert_called_once()

    @patch("api.routes.admin.background_task_manager")
    def test_get_background_tasks_status(self, mock_task_manager):
        """Test getting background tasks status."""
        # Mock task status
        mock_task_status = {
            "cache_refresh": {"is_running": True, "interval_seconds": 900, "run_count": 5, "error_count": 0},
            "test_task": {"is_running": False, "interval_seconds": 60, "run_count": 10, "error_count": 1},
        }
        mock_task_manager.get_all_task_status.return_value = mock_task_status

        response = self.client.get("/admin/background-tasks")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("tasks", data)
        self.assertIn("total_tasks", data)
        self.assertEqual(data["total_tasks"], 2)
        self.assertEqual(data["tasks"], mock_task_status)

    @patch("api.routes.admin.background_task_manager")
    def test_get_background_tasks_status_error(self, mock_task_manager):
        """Test background tasks status endpoint error handling."""
        mock_task_manager.get_all_task_status.side_effect = Exception("Test error")

        response = self.client.get("/admin/background-tasks")
        self.assertEqual(response.status_code, 500)

        data = response.json()
        self.assertIn("Failed to retrieve background tasks status", data["detail"])

    @patch("api.routes.admin.background_task_manager")
    def test_cancel_background_task_success(self, mock_task_manager):
        """Test successfully cancelling a background task."""
        mock_task_manager.cancel_task = AsyncMock(return_value=True)

        response = self.client.post("/admin/background-tasks/test_task/cancel")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("test_task", data["message"])
        self.assertIn("cancelled successfully", data["message"])

    @patch("api.routes.admin.background_task_manager")
    def test_cancel_background_task_not_found(self, mock_task_manager):
        """Test cancelling a non-existent background task."""
        mock_task_manager.cancel_task = AsyncMock(return_value=False)

        response = self.client.post("/admin/background-tasks/nonexistent_task/cancel")
        self.assertEqual(response.status_code, 404)

        data = response.json()
        self.assertIn("not found", data["detail"])

    @patch("api.routes.admin.background_task_manager")
    def test_cancel_background_task_error(self, mock_task_manager):
        """Test error handling when cancelling a background task."""
        mock_task_manager.cancel_task = AsyncMock(side_effect=Exception("Test error"))

        response = self.client.post("/admin/background-tasks/test_task/cancel")
        self.assertEqual(response.status_code, 500)

        data = response.json()
        self.assertIn("Failed to cancel task", data["detail"])

    @patch("api.routes.admin.background_task_manager")
    def test_admin_endpoints_integration(self, mock_task_manager):
        """Test integration of multiple admin endpoints."""
        # Mock background task manager
        mock_task_manager.get_all_task_status.return_value = {"cache_refresh": {"is_running": True}}
        mock_task_manager.cancel_task = AsyncMock(return_value=True)

        # Test cache stats
        response = self.client.get("/admin/cache/stats")
        self.assertEqual(response.status_code, 200)

        # Test cache status
        response = self.client.get("/admin/cache/status")
        self.assertEqual(response.status_code, 200)

        # Test background tasks status
        response = self.client.get("/admin/background-tasks")
        self.assertEqual(response.status_code, 200)

        # Test cache invalidation
        response = self.client.post("/admin/cache/invalidate/prompts")
        self.assertEqual(response.status_code, 200)

        # Test cache reload
        response = self.client.post("/admin/cache/reload")
        self.assertEqual(response.status_code, 200)

        # Test cache refresh
        response = self.client.post("/admin/cache/refresh")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
