"""
Background task manager for periodic operations.

This module provides utilities for managing background tasks that run
periodically, such as cache refresh operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional


class BackgroundTaskManager:
    """Manages background tasks with periodic execution."""

    def __init__(self):
        self.tasks: Dict[str, asyncio.Task] = {}
        self.task_info: Dict[str, Dict[str, Any]] = {}
        self._shutdown = False

    async def create_periodic_task(
        self,
        name: str,
        coro_func: Callable[[], Any],
        interval_seconds: float,
        run_immediately: bool = True,
    ) -> None:
        """
        Create a periodic background task.

        Args:
            name: Unique name for the task
            coro_func: Async function to run periodically
            interval_seconds: Interval between executions in seconds
            run_immediately: Whether to run the task immediately on creation
        """
        if name in self.tasks:
            logging.warning(f"Task '{name}' already exists, cancelling existing task")
            await self.cancel_task(name)

        task = asyncio.create_task(self._periodic_task_runner(name, coro_func, interval_seconds, run_immediately))
        self.tasks[name] = task
        self.task_info[name] = {
            "interval_seconds": interval_seconds,
            "created_at": datetime.now(),
            "last_run": None,
            "next_run": datetime.now() if run_immediately else datetime.now() + timedelta(seconds=interval_seconds),
            "run_count": 0,
            "error_count": 0,
            "last_error": None,
        }
        logging.info(f"Created periodic task '{name}' with {interval_seconds}s interval")

    async def _periodic_task_runner(
        self, name: str, coro_func: Callable[[], Any], interval_seconds: float, run_immediately: bool
    ) -> None:
        """Internal runner for periodic tasks."""
        try:
            if not run_immediately:
                await asyncio.sleep(interval_seconds)

            while not self._shutdown:
                try:
                    logging.debug(f"Running periodic task: {name}")
                    start_time = datetime.now()

                    # Run the task
                    await coro_func()

                    # Update task info
                    self.task_info[name]["last_run"] = start_time
                    self.task_info[name]["next_run"] = datetime.now() + timedelta(seconds=interval_seconds)
                    self.task_info[name]["run_count"] += 1

                    logging.debug(f"Completed periodic task: {name}")

                except Exception as e:
                    logging.error(f"Error in periodic task '{name}': {e}")
                    self.task_info[name]["error_count"] += 1
                    self.task_info[name]["last_error"] = str(e)

                # Wait for next execution
                await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logging.info(f"Periodic task '{name}' was cancelled")
            raise
        except Exception as e:
            logging.error(f"Fatal error in periodic task '{name}': {e}")

    async def cancel_task(self, name: str) -> bool:
        """
        Cancel a background task.

        Args:
            name: Name of the task to cancel

        Returns:
            bool: True if task was cancelled, False if task didn't exist
        """
        if name not in self.tasks:
            logging.warning(f"Task '{name}' not found for cancellation")
            return False

        task = self.tasks[name]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        del self.tasks[name]
        if name in self.task_info:
            del self.task_info[name]

        logging.info(f"Cancelled background task: {name}")
        return True

    async def cancel_all_tasks(self) -> None:
        """Cancel all background tasks."""
        self._shutdown = True
        task_names = list(self.tasks.keys())

        for name in task_names:
            await self.cancel_task(name)

        logging.info(f"Cancelled all {len(task_names)} background tasks")

    def get_task_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get status information for a task.

        Args:
            name: Name of the task

        Returns:
            Optional[Dict]: Task status info or None if task doesn't exist
        """
        if name not in self.task_info:
            return None

        info = self.task_info[name].copy()
        task = self.tasks.get(name)

        if task:
            info["is_running"] = not task.done()
            info["is_cancelled"] = task.cancelled()
            if task.done() and not task.cancelled():
                info["exception"] = task.exception()
        else:
            info["is_running"] = False
            info["is_cancelled"] = True

        return info

    def get_all_task_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all tasks."""
        result = {}
        for name in self.task_info:
            status = self.get_task_status(name)
            if status is not None:
                result[name] = status
        return result

    def is_task_running(self, name: str) -> bool:
        """Check if a task is currently running."""
        if name not in self.tasks:
            return False

        task = self.tasks[name]
        return not task.done()


# Global instance
background_task_manager = BackgroundTaskManager()
