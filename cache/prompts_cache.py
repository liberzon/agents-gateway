import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from cachetools import TTLCache

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Cache configuration
CACHE_TTL = 60 * 60  # 60 minutes in seconds
CACHE_MAXSIZE = 1000  # Increased for full cache loading
REFRESH_INTERVAL = 15 * 60  # 15 minutes in seconds - kept for backward compatibility

# Prompt caches
prompt_cache: TTLCache[str, Any] = TTLCache(
    maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL
)  # key: prompt_service_id, value: prompt
prompts_list_cache: Dict[str, List[str]] = {}  # key: 'all', value: list of prompt names
prompts_list_timestamp = 0  # Last time the prompts_list_cache was updated

# Cache state tracking
is_cache_initialized = False
cache_initialization_time: Optional[datetime] = None
last_full_refresh_time: Optional[datetime] = None
cache_statistics = {
    "total_prompts_loaded": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "full_refreshes": 0,
    "partial_refreshes": 0,
    "load_errors": 0,
    "prompts_updated": 0,
    "prompts_skipped_unchanged": 0,
}


def invalidate_prompt_cache(prompt_id=None):
    global prompts_list_cache, prompts_list_timestamp, is_cache_initialized

    logging.info(f"Invalidating prompt cache: {'all prompts' if prompt_id is None else prompt_id}")

    if prompt_id is None:
        # Invalidate all prompt caches
        prompts_list_cache.clear()
        prompts_list_timestamp = 0
        prompt_cache.clear()
        is_cache_initialized = False
        logging.info("All prompt caches invalidated")
    else:
        # Invalidate specific prompt cache
        if prompt_id in prompt_cache:
            del prompt_cache[prompt_id]
            logging.debug(f"Removed prompt '{prompt_id}' from cache")
        # Force refresh of prompts list on next request
        prompts_list_cache.clear()
        prompts_list_timestamp = 0
        logging.debug(f"Forced refresh of prompts list due to change in '{prompt_id}'")


async def load_all_prompts_to_cache(db: "Session | None" = None):
    """Load all prompts to cache using the configured storage backend.

    Args:
        db: SQLAlchemy session (required for postgres backend)
    """
    global is_cache_initialized, cache_initialization_time, cache_statistics

    backend = os.getenv("PROMPT_STORAGE_BACKEND", "postgres").lower()

    # Check if service backend is configured but SERVICE_PROMPTS is not set
    if backend == "service" and not os.getenv("SERVICE_PROMPTS"):
        logging.info("Prompts service backend configured but SERVICE_PROMPTS not set, skipping cache init")
        is_cache_initialized = True  # Mark as initialized to avoid waiting
        return

    logging.info(f"Starting full cache initialization (backend: {backend})")
    start_time = datetime.now()

    try:
        from prompts.storage import get_prompt_storage

        # Get storage backend
        try:
            storage = get_prompt_storage(db)
        except ValueError as e:
            # Postgres backend requires DB session
            if "database session" in str(e).lower() and db is None:
                logging.info("Postgres backend requires DB session, skipping startup cache init (will cache on demand)")
                is_cache_initialized = True
                return
            raise

        # Load all prompts from storage
        prompts = storage.get_all()

        for prompt in prompts:
            store_prompt_with_hash(prompt.id, prompt)

        is_cache_initialized = True
        cache_initialization_time = datetime.now()
        cache_statistics["total_prompts_loaded"] = len(prompt_cache)

        duration = (datetime.now() - start_time).total_seconds()
        logging.info(f"Cache initialization completed in {duration:.2f}s with {len(prompt_cache)} prompts")

    except Exception as e:
        cache_statistics["load_errors"] += 1
        logging.warning(f"Cache initialization skipped: {e}")
        # Still mark as initialized to avoid blocking
        is_cache_initialized = True


async def refresh_all_prompts(db: "Session | None" = None):
    """Refresh all prompts in cache using the configured storage backend.

    Args:
        db: SQLAlchemy session (required for postgres backend)
    """
    global last_full_refresh_time, cache_statistics

    backend = os.getenv("PROMPT_STORAGE_BACKEND", "postgres").lower()

    # Check if service backend is configured but SERVICE_PROMPTS is not set
    if backend == "service" and not os.getenv("SERVICE_PROMPTS"):
        logging.debug("Prompts service backend not configured, skipping refresh")
        return

    logging.info(f"Starting full cache refresh (backend: {backend})")
    start_time = datetime.now()

    try:
        from prompts.storage import get_prompt_storage

        # For postgres backend, we need a DB session
        # If not provided, create one
        session_to_use = db
        should_close_session = False

        if backend == "postgres" and db is None:
            from db.session import SessionLocal

            session_to_use = SessionLocal()
            should_close_session = True

        try:
            storage = get_prompt_storage(session_to_use)
            old_count = len(prompt_cache)

            # Load all prompts and update cache
            prompts = storage.get_all()
            updated = 0
            unchanged = 0

            for prompt in prompts:
                # Check if prompt changed using hash
                old_hash = get_cached_prompt_hash(prompt.id)
                new_hash = calculate_prompt_hash(prompt)

                if old_hash != new_hash:
                    store_prompt_with_hash(prompt.id, prompt, new_hash)
                    updated += 1
                else:
                    unchanged += 1

            last_full_refresh_time = datetime.now()
            cache_statistics["full_refreshes"] += 1
            cache_statistics["total_prompts_loaded"] = len(prompt_cache)
            cache_statistics["prompts_updated"] += updated
            cache_statistics["prompts_skipped_unchanged"] += unchanged

            duration = (datetime.now() - start_time).total_seconds()
            new_count = len(prompt_cache)
            logging.info(
                f"Cache refresh completed in {duration:.2f}s ({old_count} -> {new_count} prompts, "
                f"{updated} updated, {unchanged} unchanged)"
            )

        finally:
            if should_close_session and session_to_use:
                session_to_use.close()

    except Exception as e:
        cache_statistics["load_errors"] += 1
        logging.warning(f"Cache refresh skipped: {e}")


def extend_cache_ttl(prompt_id: str):
    if prompt_id in prompt_cache:
        # Get current value and re-insert to extend TTL
        value = prompt_cache[prompt_id]
        prompt_cache[prompt_id] = value
        logging.debug(f"Extended TTL for prompt '{prompt_id}'")


def record_cache_hit(prompt_id: str):
    cache_statistics["cache_hits"] += 1
    logging.debug(f"Cache hit for prompt '{prompt_id}'")


def record_cache_miss(prompt_id: str):
    cache_statistics["cache_misses"] += 1
    logging.debug(f"Cache miss for prompt '{prompt_id}'")


def get_cache_status():
    next_sync_time = calculate_next_sync_time()
    return {
        "is_initialized": is_cache_initialized,
        "initialization_time": cache_initialization_time.isoformat() if cache_initialization_time else None,
        "last_refresh_time": last_full_refresh_time.isoformat() if last_full_refresh_time else None,
        "next_refresh_time": next_sync_time.isoformat(),
        "seconds_until_next_refresh": get_seconds_until_next_sync(),
        "cache_size": len(prompt_cache),
        "cache_maxsize": prompt_cache.maxsize,
        "cache_ttl_seconds": prompt_cache.ttl,
        "refresh_interval_seconds": REFRESH_INTERVAL,  # Kept for backward compatibility
        "refresh_pattern": "synchronized at 0, 15, 30, 45 minutes of each hour",
        "statistics": cache_statistics.copy(),
    }


async def wait_for_cache_ready(timeout_seconds: float = 30) -> bool:
    logging.debug(f"Waiting for cache to be ready (timeout: {timeout_seconds}s)")

    end_time = time.time() + timeout_seconds
    while time.time() < end_time:
        if is_cache_initialized:
            logging.debug("Cache is ready")
            return True
        await asyncio.sleep(0.1)

    logging.warning(f"Cache not ready after {timeout_seconds}s timeout")
    return False


def calculate_next_sync_time() -> datetime:
    """
    Calculate the next synchronized refresh time.
    Refreshes happen at exactly 0, 15, 30, and 45 minutes of each hour.

    Returns:
        datetime: The next scheduled refresh time
    """
    now = datetime.now()
    # Get the current minute
    current_minute = now.minute

    # Define the sync minutes: 0, 15, 30, 45
    sync_minutes = [0, 15, 30, 45]

    # Find the next sync minute
    next_minute = None
    for minute in sync_minutes:
        if current_minute < minute:
            next_minute = minute
            break

    if next_minute is None:
        # All sync times for this hour have passed, go to next hour at minute 0
        next_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        # Use the next sync minute in this hour
        next_time = now.replace(minute=next_minute, second=0, microsecond=0)

    return next_time


def get_seconds_until_next_sync() -> int:
    """
    Get the number of seconds until the next synchronized refresh time.

    Returns:
        int: Seconds until next sync time
    """
    now = datetime.now()
    next_sync = calculate_next_sync_time()
    delta = next_sync - now

    # Ensure we return at least 1 second to avoid immediate execution
    return max(1, int(delta.total_seconds()))


async def synchronized_refresh_loop():
    """
    Run synchronized cache refreshes at 0, 15, 30, 45 minutes of each hour.
    This function should be run as a background task.
    """
    logging.info("Starting synchronized cache refresh loop")

    while True:
        try:
            # Calculate time until next sync
            seconds_until_sync = get_seconds_until_next_sync()
            next_sync_time = calculate_next_sync_time()

            logging.info(
                f"Next synchronized cache refresh scheduled for {next_sync_time.strftime('%H:%M:%S')} "
                f"(in {seconds_until_sync} seconds)"
            )

            # Wait until the next sync time
            await asyncio.sleep(seconds_until_sync)

            # Perform the refresh
            logging.info(f"Executing synchronized cache refresh at {datetime.now().strftime('%H:%M:%S')}")
            await refresh_all_prompts()

        except asyncio.CancelledError:
            logging.info("Synchronized cache refresh loop cancelled")
            break
        except Exception as e:
            logging.error(f"Error in synchronized cache refresh loop: {e}")
            # Wait a bit before retrying to avoid rapid failures
            await asyncio.sleep(60)


def calculate_prompt_hash(prompt_response) -> str:
    """
    Calculate a hash of the prompt content for change detection.

    Args:
        prompt_response: PullPromptResponse object or similar

    Returns:
        str: SHA256 hash of the prompt content
    """
    # Create a dictionary with the content we care about for change detection
    content = {
        "template": getattr(prompt_response, "template", ""),
        "description": getattr(prompt_response, "description", ""),
        "tags": getattr(prompt_response, "tags", []) or [],
        "tools": getattr(prompt_response, "tools", []) or [],
    }

    # Convert to JSON string for consistent hashing
    content_str = json.dumps(content, sort_keys=True, ensure_ascii=True)

    # Calculate SHA256 hash
    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def get_cached_prompt_hash(prompt_name: str) -> Optional[str]:
    """
    Get the stored hash for a cached prompt.

    Args:
        prompt_name: Name of the prompt

    Returns:
        Optional[str]: Hash of the cached prompt, or None if not cached or no hash stored
    """
    cached_data = prompt_cache.get(prompt_name)
    if not cached_data:
        return None

    # Handle both new format (dict with hash) and old format (direct prompt object)
    if isinstance(cached_data, dict) and "_cache_hash" in cached_data:
        return cached_data["_cache_hash"]

    return None


def store_prompt_with_hash(prompt_name: str, prompt_response, content_hash: Optional[str] = None):
    """
    Store a prompt in cache along with its content hash.

    Args:
        prompt_name: Name of the prompt
        prompt_response: The prompt response object
        content_hash: Optional pre-calculated hash, will calculate if not provided
    """
    if content_hash is None:
        content_hash = calculate_prompt_hash(prompt_response)

    # Store in a format that includes both the prompt and its hash
    cache_entry = {"prompt": prompt_response, "_cache_hash": content_hash, "_cached_at": datetime.now().isoformat()}

    prompt_cache[prompt_name] = cache_entry
    logging.debug(f"Stored prompt '{prompt_name}' with hash {content_hash[:8]}...")


def get_cached_prompt(prompt_name: str):
    """
    Get a cached prompt (unwrapped from cache entry format).

    Args:
        prompt_name: Name of the prompt

    Returns:
        The prompt response object, or None if not cached
    """
    cached_data = prompt_cache.get(prompt_name)
    if not cached_data:
        return None

    # Handle both new format (dict with prompt) and old format (direct prompt object)
    if isinstance(cached_data, dict) and "prompt" in cached_data:
        return cached_data["prompt"]

    # Backward compatibility with old cache format
    return cached_data
