#!/usr/bin/env python3
"""
Script to verify that a migration has been applied successfully.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add parent directory to path so we can import from db package
sys.path.append(str(Path(__file__).parent.parent.parent))

from db.url import get_db_url


def verify_is_estimated_column():
    """
    Verify that the is_estimated column exists in the token_usage table.
    """
    # Get database URL
    db_url = get_db_url()

    # Create engine
    engine = create_engine(db_url)

    # Check if the column exists
    inspector = inspect(engine)
    columns = inspector.get_columns("token_usage")
    column_names = [col["name"] for col in columns]

    if "is_estimated" in column_names:
        print("✅ The 'is_estimated' column exists in the token_usage table.")

        # Get column details
        is_estimated_col = next(col for col in columns if col["name"] == "is_estimated")
        print(f"   Type: {is_estimated_col['type']}")
        print(f"   Nullable: {is_estimated_col['nullable']}")

        # Check if there are any rows in the table
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM token_usage"))
            count = result.scalar() or 0

            if count > 0:
                # Check if there are any NULL values in the is_estimated column
                result = conn.execute(text("SELECT COUNT(*) FROM token_usage WHERE is_estimated IS NULL"))
                null_count = result.scalar() or 0

                if null_count == 0:
                    print(f"✅ All {count} rows have a value for is_estimated.")
                else:
                    print(f"❌ {null_count} out of {count} rows have NULL values for is_estimated.")

                # Check if there are any estimated token counts
                result = conn.execute(text("SELECT COUNT(*) FROM token_usage WHERE is_estimated = TRUE"))
                estimated_count = result.scalar() or 0

                if estimated_count > 0:
                    print(f"ℹ️ {estimated_count} out of {count} rows have estimated token counts.")
                else:
                    print("ℹ️ No rows have estimated token counts yet.")
    else:
        print("❌ The 'is_estimated' column does not exist in the token_usage table.")
        print("   Please run the migration script to add the column.")


if __name__ == "__main__":
    verify_is_estimated_column()
