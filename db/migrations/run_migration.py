#!/usr/bin/env python3
"""
Script to run SQL migration files against the database.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add parent directory to path so we can import from db package
sys.path.append(str(Path(__file__).parent.parent.parent))

from db.url import get_db_url


def run_migration(migration_file: str) -> None:
    """
    Run a SQL migration file against the database.

    Args:
        migration_file: Path to the SQL migration file
    """
    if not os.path.exists(migration_file):
        print(f"Error: Migration file {migration_file} does not exist")
        sys.exit(1)

    # Read the SQL from the file
    with open(migration_file, "r") as f:
        sql = f.read()

    # Get database URL
    db_url = get_db_url()

    # Print the URL for debugging (without password)
    print(f"Database URL: {db_url.replace(db_url.split('@')[0], '***')}")

    # Create engine
    engine = create_engine(db_url)

    # Execute the SQL
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        print(f"Successfully applied migration: {migration_file}")
    except Exception as e:
        print(f"Error applying migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_migration.py <migration_file>")
        print("Example: python run_migration.py add_is_estimated_column.sql")
        sys.exit(1)

    migration_file = sys.argv[1]

    # If only filename is provided, assume it's in the same directory
    if not os.path.dirname(migration_file):
        migration_file = os.path.join(os.path.dirname(__file__), migration_file)

    run_migration(migration_file)
