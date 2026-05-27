import asyncio
import unittest
from datetime import datetime

from cache.background_tasks import BackgroundTaskManager


class TestBackgroundTaskManager(unittest.TestCase):
    def setUp(self):
        self.manager = BackgroundTaskManager()

    async def async_tearDown(self):
        await self.manager.cancel_all_tasks()

    def tearDown(self):
        asyncio.run(self.async_tearDown())

    def test_create_periodic_task(self):
        """Test creating a periodic background task."""

        async def test_task():
            return "test_result"

        # Run the async test
        async def run_test():
            await self.manager.create_periodic_task(
                name="test_task", coro_func=test_task, interval_seconds=1, run_immediately=False
            )

            # Check task was created
            self.assertIn("test_task", self.manager.tasks)
            self.assertTrue(self.manager.is_task_running("test_task"))

            # Check task info
            task_info = self.manager.get_task_status("test_task")
            self.assertIsNotNone(task_info)
            assert task_info is not None  # Type narrowing for mypy
            self.assertEqual(task_info["interval_seconds"], 1)
            self.assertFalse(task_info["is_cancelled"])

        asyncio.run(run_test())

    def test_cancel_background_task(self):
        """Test cancelling a background task."""

        async def test_task():
            await asyncio.sleep(0.1)

        async def run_test():
            # Create task
            await self.manager.create_periodic_task(
                name="test_task", coro_func=test_task, interval_seconds=1, run_immediately=False
            )

            # Verify task is running
            self.assertTrue(self.manager.is_task_running("test_task"))

            # Cancel task
            success = await self.manager.cancel_task("test_task")
            self.assertTrue(success)

            # Verify task is cancelled
            self.assertFalse(self.manager.is_task_running("test_task"))
            self.assertNotIn("test_task", self.manager.tasks)

        asyncio.run(run_test())

    def test_cancel_nonexistent_task(self):
        """Test cancelling a task that doesn't exist."""

        async def run_test():
            success = await self.manager.cancel_task("nonexistent_task")
            self.assertFalse(success)

        asyncio.run(run_test())

    def test_task_exception_handling(self):
        """Test that task exceptions are handled gracefully."""

        async def failing_task():
            raise ValueError("Test error")

        async def run_test():
            await self.manager.create_periodic_task(
                name="failing_task", coro_func=failing_task, interval_seconds=0.1, run_immediately=True
            )

            # Wait a bit for the task to run and fail
            await asyncio.sleep(0.2)

            # Task should still be running despite the error
            self.assertTrue(self.manager.is_task_running("failing_task"))

            # Check error was recorded
            task_info = self.manager.get_task_status("failing_task")
            self.assertIsNotNone(task_info)
            assert task_info is not None  # Type narrowing for mypy
            self.assertGreater(task_info["error_count"], 0)
            self.assertIsNotNone(task_info["last_error"])
            self.assertIn("Test error", task_info["last_error"])

        asyncio.run(run_test())

    def test_multiple_tasks_concurrent(self):
        """Test running multiple background tasks concurrently."""
        task1_calls = 0
        task2_calls = 0

        async def task1():
            nonlocal task1_calls
            task1_calls += 1

        async def task2():
            nonlocal task2_calls
            task2_calls += 1

        async def run_test():
            # Create two tasks
            await self.manager.create_periodic_task(
                name="task1", coro_func=task1, interval_seconds=0.1, run_immediately=True
            )

            await self.manager.create_periodic_task(
                name="task2", coro_func=task2, interval_seconds=0.15, run_immediately=True
            )

            # Wait for tasks to run
            await asyncio.sleep(0.3)

            # Both tasks should be running
            self.assertTrue(self.manager.is_task_running("task1"))
            self.assertTrue(self.manager.is_task_running("task2"))

            # Both tasks should have been called
            self.assertGreater(task1_calls, 0)
            self.assertGreater(task2_calls, 0)

            # Get status for both tasks
            all_status = self.manager.get_all_task_status()
            self.assertEqual(len(all_status), 2)
            self.assertIn("task1", all_status)
            self.assertIn("task2", all_status)

        asyncio.run(run_test())

    def test_cancel_all_tasks(self):
        """Test cancelling all background tasks."""

        async def test_task():
            await asyncio.sleep(0.1)

        async def run_test():
            # Create multiple tasks
            await self.manager.create_periodic_task(
                name="task1", coro_func=test_task, interval_seconds=1, run_immediately=False
            )

            await self.manager.create_periodic_task(
                name="task2", coro_func=test_task, interval_seconds=1, run_immediately=False
            )

            # Verify both tasks are running
            self.assertEqual(len(self.manager.tasks), 2)

            # Cancel all tasks
            await self.manager.cancel_all_tasks()

            # Verify all tasks are cancelled
            self.assertEqual(len(self.manager.tasks), 0)
            self.assertFalse(self.manager.is_task_running("task1"))
            self.assertFalse(self.manager.is_task_running("task2"))

        asyncio.run(run_test())

    def test_task_run_immediately_flag(self):
        """Test the run_immediately flag functionality."""

        async def run_test():
            task_calls = 0

            async def test_task():
                nonlocal task_calls
                task_calls += 1

            # Create task with run_immediately=True
            await self.manager.create_periodic_task(
                name="immediate_task",
                coro_func=test_task,
                interval_seconds=10,  # Long interval
                run_immediately=True,
            )

            # Wait a short time
            await asyncio.sleep(0.1)

            # Task should have been called immediately
            self.assertGreater(task_calls, 0)

            # Reset counter and test run_immediately=False
            task_calls = 0

            await self.manager.cancel_task("immediate_task")

            await self.manager.create_periodic_task(
                name="delayed_task", coro_func=test_task, interval_seconds=0.1, run_immediately=False
            )

            # Wait less than the interval
            await asyncio.sleep(0.05)

            # Task should not have been called yet
            self.assertEqual(task_calls, 0)

        asyncio.run(run_test())

    def test_task_status_tracking(self):
        """Test that task status is properly tracked."""

        async def test_task():
            await asyncio.sleep(0.01)

        async def run_test():
            start_time = datetime.now()

            await self.manager.create_periodic_task(
                name="status_task", coro_func=test_task, interval_seconds=0.1, run_immediately=True
            )

            # Wait for at least one execution
            await asyncio.sleep(0.15)

            status = self.manager.get_task_status("status_task")
            self.assertIsNotNone(status)
            assert status is not None  # Type narrowing for mypy

            # Check basic status fields
            self.assertEqual(status["interval_seconds"], 0.1)
            self.assertTrue(status["created_at"] >= start_time)
            self.assertIsNotNone(status["last_run"])
            self.assertIsNotNone(status["next_run"])
            self.assertGreater(status["run_count"], 0)
            self.assertEqual(status["error_count"], 0)
            self.assertTrue(status["is_running"])
            self.assertFalse(status["is_cancelled"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
