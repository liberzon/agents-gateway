#!/usr/bin/env python3
"""
Migration script to migrate prompts from LangSmith to PostgreSQL.

This script:
1. Fetches all prompts from LangSmith Hub
2. Creates corresponding records in the PostgreSQL database
3. Optionally verifies the migration

Usage:
    python scripts/migrate_prompts_from_langsmith.py [--dry-run] [--prompt-ids id1,id2,...]

Environment variables required:
    LANGCHAIN_API_KEY: LangSmith API key
    DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_DATABASE: Database connection
"""

import argparse
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_langsmith_prompts(prompt_ids: list[str] | None = None) -> list[dict]:
    """Fetch prompts from LangSmith Hub.

    Args:
        prompt_ids: Optional list of specific prompt IDs to fetch

    Returns:
        List of prompt dictionaries
    """
    try:
        from langsmith import Client, hub  # type: ignore[import-not-found]
    except ImportError:
        logger.error("LangSmith package not installed. Run: pip install langsmith")
        sys.exit(1)

    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        logger.error("LANGCHAIN_API_KEY environment variable not set")
        sys.exit(1)

    # Initialize client (used internally by hub.pull)
    _ = Client(api_key=api_key)
    prompts = []

    if prompt_ids:
        # Fetch specific prompts
        for prompt_id in prompt_ids:
            try:
                prompt = hub.pull(prompt_id)
                # Extract template from prompt object
                if hasattr(prompt, "messages") and prompt.messages:
                    template = str(prompt.messages[0].prompt.template)
                elif hasattr(prompt, "template"):
                    template = prompt.template
                else:
                    template = str(prompt)

                prompts.append(
                    {
                        "id": prompt_id,
                        "name": prompt_id,
                        "template": template,
                        "description": "Migrated from LangSmith Hub",
                    }
                )
                logger.info(f"Fetched prompt: {prompt_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch prompt {prompt_id}: {e}")
    else:
        # Note: LangSmith Hub doesn't have a simple list API
        # This would need to be implemented based on your specific setup
        logger.warning("No prompt IDs specified. Use --prompt-ids to specify prompts to migrate.")

    return prompts


def migrate_to_postgres(prompts: list[dict], dry_run: bool = False) -> tuple[int, int]:
    """Migrate prompts to PostgreSQL.

    Args:
        prompts: List of prompt dictionaries
        dry_run: If True, don't actually write to database

    Returns:
        Tuple of (success_count, failure_count)
    """
    from db.session import SessionLocal
    from prompts.storage.postgres import PostgresStorage

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    success = 0
    failure = 0

    with SessionLocal() as db:
        storage = PostgresStorage(db)

        for prompt in prompts:
            prompt_id = prompt["id"]
            try:
                if dry_run:
                    if storage.exists(prompt_id):
                        logger.info(f"[DRY RUN] Would skip existing prompt: {prompt_id}")
                    else:
                        logger.info(f"[DRY RUN] Would create prompt: {prompt_id}")
                    success += 1
                else:
                    if storage.exists(prompt_id):
                        logger.info(f"Skipping existing prompt: {prompt_id}")
                        success += 1
                        continue

                    storage.create(
                        prompt_id=prompt_id,
                        name=prompt.get("name", prompt_id),
                        template=prompt["template"],
                        description=prompt.get("description"),
                        tags=prompt.get("tags", []),
                        tools=prompt.get("tools", []),
                    )
                    logger.info(f"Migrated prompt: {prompt_id}")
                    success += 1

            except Exception as e:
                logger.error(f"Failed to migrate prompt {prompt_id}: {e}")
                failure += 1

    return success, failure


def verify_migration(prompt_ids: list[str]) -> bool:
    """Verify that prompts were migrated correctly.

    Args:
        prompt_ids: List of prompt IDs to verify

    Returns:
        True if all prompts exist, False otherwise
    """
    from db.session import SessionLocal
    from prompts.storage.postgres import PostgresStorage

    with SessionLocal() as db:
        storage = PostgresStorage(db)

        all_exist = True
        for prompt_id in prompt_ids:
            prompt = storage.get(prompt_id)
            if prompt:
                logger.info(f"Verified: {prompt_id} exists (version {prompt.version})")
            else:
                logger.error(f"Missing: {prompt_id}")
                all_exist = False

    return all_exist


def main():
    parser = argparse.ArgumentParser(description="Migrate prompts from LangSmith to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing to database")
    parser.add_argument("--prompt-ids", type=str, help="Comma-separated list of prompt IDs to migrate")
    parser.add_argument("--verify", action="store_true", help="Verify migration after completion")

    args = parser.parse_args()

    # Parse prompt IDs
    prompt_ids = None
    if args.prompt_ids:
        prompt_ids = [p.strip() for p in args.prompt_ids.split(",")]

    if not prompt_ids:
        logger.error("Please specify prompt IDs with --prompt-ids")
        sys.exit(1)

    # Fetch from LangSmith
    logger.info(f"Fetching {len(prompt_ids)} prompts from LangSmith...")
    prompts = get_langsmith_prompts(prompt_ids)

    if not prompts:
        logger.warning("No prompts to migrate")
        sys.exit(0)

    logger.info(f"Found {len(prompts)} prompts to migrate")

    # Migrate to PostgreSQL
    logger.info("Migrating to PostgreSQL...")
    success, failure = migrate_to_postgres(prompts, dry_run=args.dry_run)

    logger.info(f"Migration complete: {success} succeeded, {failure} failed")

    # Verify if requested
    if args.verify and not args.dry_run:
        logger.info("Verifying migration...")
        if verify_migration(prompt_ids):
            logger.info("Verification passed!")
        else:
            logger.error("Verification failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
