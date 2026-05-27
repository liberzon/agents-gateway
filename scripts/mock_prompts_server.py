#!/usr/bin/env python3
"""
Mock Prompts Server with Persistent Caching

A development server that caches responses from the real prompts service to disk,
allowing for faster local development and offline work.

Usage:
    # Start the mock server (default port 8001)
    python scripts/mock_prompts_server.py

    # Use custom port
    python scripts/mock_prompts_server.py --port 8002

    # Clear cache and re-fetch from real service
    python scripts/mock_prompts_server.py --clear-cache

    # Then configure your app to use the mock server:
    export SERVICE_PROMPTS=http://localhost:8001
"""

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.agent_utils import call_cloud_run_service

# Configuration
CACHE_DIR = Path(__file__).parent.parent / ".prompts_cache"
CACHE_DIR.mkdir(exist_ok=True)

PROMPTS_LIST_FILE = CACHE_DIR / "prompts_list.json"
PROMPTS_DIR = CACHE_DIR / "prompts"
PROMPTS_DIR.mkdir(exist_ok=True)

# Real prompts service URL from environment

REAL_SERVICE_URL = os.getenv("SERVICE_PROMPTS_REAL")
SERVICE_KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or str(
    Path(__file__).parent.parent / "agents" / "service-account.json"
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mock Prompts Server",
    description="Development server with caching for prompts service",
    version="1.0.0",
)


def _get_cache_file(prompt_name: str) -> Path:
    """Get cache file path for a prompt."""
    # Use hash to handle special characters in prompt names
    name_hash = hashlib.md5(prompt_name.encode()).hexdigest()
    return PROMPTS_DIR / f"{name_hash}.json"


def _save_to_cache(prompt_name: str, data: Dict[str, Any]) -> None:
    """Save prompt data to cache."""
    cache_file = _get_cache_file(prompt_name)
    cache_data = {
        "prompt_name": prompt_name,
        "data": data,
    }
    cache_file.write_text(json.dumps(cache_data, indent=2))
    logger.info(f"Cached prompt: {prompt_name}")


def _load_from_cache(prompt_name: str) -> Optional[Dict[str, Any]]:
    """Load prompt data from cache."""
    cache_file = _get_cache_file(prompt_name)
    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            logger.info(f"Cache hit: {prompt_name}")
            return cache_data["data"]
        except Exception as e:
            logger.error(f"Error loading cache for {prompt_name}: {e}")
            return None
    return None


def _save_prompts_list(prompts: List[str]) -> None:
    """Save prompts list to cache."""
    PROMPTS_LIST_FILE.write_text(json.dumps({"prompts": prompts}, indent=2))
    logger.info(f"Cached prompts list: {len(prompts)} prompts")


def _load_prompts_list() -> Optional[List[str]]:
    """Load prompts list from cache."""
    if PROMPTS_LIST_FILE.exists():
        try:
            data = json.loads(PROMPTS_LIST_FILE.read_text())
            logger.info(f"Cache hit: prompts list ({len(data['prompts'])} prompts)")
            return data["prompts"]
        except Exception as e:
            logger.error(f"Error loading prompts list cache: {e}")
            return None
    return None


def _fetch_from_real_service(endpoint: str = "") -> Dict[str, Any]:
    """Fetch data from real prompts service."""
    if not REAL_SERVICE_URL:
        raise HTTPException(
            status_code=503,
            detail="Real prompts service URL not configured. Set SERVICE_PROMPTS_REAL environment variable.",
        )

    if not Path(SERVICE_KEY_PATH).exists():
        raise HTTPException(
            status_code=503,
            detail=f"Service account key not found at {SERVICE_KEY_PATH}",
        )

    try:
        url = f"{REAL_SERVICE_URL.rstrip('/')}/{endpoint.lstrip('/')}" if endpoint else REAL_SERVICE_URL
        logger.info(f"Fetching from real service: {url}")
        response = call_cloud_run_service(service_url=url, service_key_path=SERVICE_KEY_PATH)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from real service: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to fetch from real prompts service: {str(e)}")


@app.get("/")
async def list_prompts(force_refresh: bool = False):
    """
    Get list of all prompts.

    Query params:
        force_refresh: If true, bypass cache and fetch from real service
    """
    # Try cache first unless force_refresh
    if not force_refresh:
        cached_prompts = _load_prompts_list()
        if cached_prompts is not None:
            return {"prompts": cached_prompts}

    # Fetch from real service
    data = _fetch_from_real_service()
    prompts = data.get("prompts", [])

    # Save to cache
    _save_prompts_list(prompts)

    return {"prompts": prompts}


@app.get("/{prompt_name}")
async def get_prompt(prompt_name: str, force_refresh: bool = False):
    """
    Get a specific prompt by name.

    Path params:
        prompt_name: Name of the prompt to retrieve

    Query params:
        force_refresh: If true, bypass cache and fetch from real service
    """
    # Try cache first unless force_refresh
    if not force_refresh:
        cached_data = _load_from_cache(prompt_name)
        if cached_data is not None:
            return cached_data

    # Fetch from real service
    data = _fetch_from_real_service(prompt_name)

    # Save to cache
    _save_to_cache(prompt_name, data)

    return data


@app.post("/cache/clear")
async def clear_cache():
    """Clear all cached data."""
    try:
        if PROMPTS_LIST_FILE.exists():
            PROMPTS_LIST_FILE.unlink()
        if PROMPTS_DIR.exists():
            shutil.rmtree(PROMPTS_DIR)
            PROMPTS_DIR.mkdir()
        logger.info("Cache cleared successfully")
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics."""
    prompts_list_cached = PROMPTS_LIST_FILE.exists()
    cached_prompts_count = len(list(PROMPTS_DIR.glob("*.json")))

    prompts_list = _load_prompts_list() or []
    total_prompts = len(prompts_list)

    return {
        "cache_directory": str(CACHE_DIR),
        "prompts_list_cached": prompts_list_cached,
        "total_prompts": total_prompts,
        "cached_prompts": cached_prompts_count,
        "cache_coverage": f"{cached_prompts_count}/{total_prompts}" if total_prompts > 0 else "0/0",
        "cache_hit_rate": f"{(cached_prompts_count / total_prompts * 100):.1f}%" if total_prompts > 0 else "N/A",
    }


@app.post("/cache/warm")
async def warm_cache():
    """
    Warm up the cache by fetching all prompts from the real service.
    This is useful for initial setup or after clearing cache.
    """
    try:
        # Fetch prompts list
        data = _fetch_from_real_service()
        prompts = data.get("prompts", [])
        _save_prompts_list(prompts)

        # Fetch each prompt
        success_count = 0
        error_count = 0

        for prompt_name in prompts:
            try:
                prompt_data = _fetch_from_real_service(prompt_name)
                _save_to_cache(prompt_name, prompt_data)
                success_count += 1
            except Exception as e:
                logger.error(f"Error fetching prompt {prompt_name}: {e}")
                error_count += 1

        return {
            "message": "Cache warming completed",
            "total_prompts": len(prompts),
            "success": success_count,
            "errors": error_count,
        }
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to warm cache: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "mock-prompts-server",
        "cache_dir": str(CACHE_DIR),
        "real_service_configured": bool(REAL_SERVICE_URL),
    }


def main():
    parser = argparse.ArgumentParser(description="Mock Prompts Server with Caching")
    parser.add_argument("--port", type=int, default=8001, help="Port to run the server on (default: 8001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--clear-cache", action="store_true", help="Clear cache before starting")
    parser.add_argument("--warm-cache", action="store_true", help="Warm cache by fetching all prompts on startup")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=args.log_level)

    # Clear cache if requested
    if args.clear_cache:
        logger.info("Clearing cache...")
        if PROMPTS_LIST_FILE.exists():
            PROMPTS_LIST_FILE.unlink()
        if PROMPTS_DIR.exists():
            shutil.rmtree(PROMPTS_DIR)
            PROMPTS_DIR.mkdir()
        logger.info("Cache cleared")

    # Print configuration
    logger.info("=" * 60)
    logger.info("Mock Prompts Server Configuration")
    logger.info("=" * 60)
    logger.info(f"Server URL:        http://{args.host}:{args.port}")
    logger.info(f"Cache directory:   {CACHE_DIR}")
    logger.info(f"Real service URL:  {REAL_SERVICE_URL or 'NOT CONFIGURED'}")
    logger.info(f"Service key:       {SERVICE_KEY_PATH}")
    logger.info("=" * 60)

    if not REAL_SERVICE_URL:
        logger.warning("⚠️  Real prompts service URL not configured!")
        logger.warning("   Set SERVICE_PROMPTS_REAL environment variable to enable proxy mode")
        logger.warning("   Server will only serve cached data")

    logger.info("")
    logger.info("Usage:")
    logger.info(f"  1. Configure your app: export SERVICE_PROMPTS=http://{args.host}:{args.port}")
    logger.info(f"  2. View cache stats:   curl http://{args.host}:{args.port}/cache/stats")
    logger.info(f"  3. Warm cache:         curl -X POST http://{args.host}:{args.port}/cache/warm")
    logger.info(f"  4. Clear cache:        curl -X POST http://{args.host}:{args.port}/cache/clear")
    logger.info("")

    # Warm cache if requested
    if args.warm_cache:
        logger.info("Warming cache on startup...")
        try:
            import requests

            response = requests.post(f"http://{args.host}:{args.port}/cache/warm", timeout=300)
            if response.ok:
                logger.info(f"Cache warming result: {response.json()}")
            else:
                logger.error(f"Cache warming failed: {response.text}")
        except Exception as e:
            logger.error(f"Error warming cache: {e}")

    # Start server
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level.lower())


if __name__ == "__main__":
    main()
