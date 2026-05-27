import logging
import os
import sys
from pathlib import Path

import uvicorn

from api.services.logging import configure_logging

# Configure logging first
configure_logging()

os.environ.setdefault("DB_DRIVER", "postgresql+psycopg")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASS", "")
os.environ.setdefault("DB_HOST", "127.0.0.1")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_DATABASE", "agentsdb")
os.environ.setdefault("SERVICE_PROMPTS", "")
os.environ.setdefault("TESTING", "false")
os.environ.setdefault("CONCURRENT_FUTURES_TIMEOUT", "180")

# Add the project root to sys.path to mimic Modal's container
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "api"))

logging.info("run_local.py: Setting up environment before importing app")


if __name__ == "__main__":
    logging.info("run_local.py: Starting server")
    # Import the app here to avoid creating it twice
    from api.main import app

    # Get host and port from environment variables or use defaults
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    logging.info(f"run_local.py: Running uvicorn with app from api.main on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
