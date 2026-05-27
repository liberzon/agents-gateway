from os import getenv
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_db_url(db_database: str = getenv("DB_DATABASE", "postgres")) -> str:
    db_driver = getenv("DB_DRIVER", "postgresql+psycopg")
    db_user = getenv("DB_USER", "postgres")
    db_pass = getenv("DB_PASS", "")
    db_host = getenv("DB_HOST")
    db_port = getenv("DB_PORT")

    # Handle case when DB_HOST is 'None' (string) or None (value)
    if db_host == "None" or db_host is None:
        db_host = "127.0.0.1"  # Default host

    # Handle case when DB_PORT is 'None' (string) or None (value)
    if db_port == "None" or db_port is None:
        db_port = "5432"  # Default PostgreSQL port

    return "{}://{}{}@{}:{}/{}".format(
        db_driver,
        quote_plus(db_user),
        f":{quote_plus(db_pass)}" if db_pass else "",
        db_host,
        db_port,
        db_database,
    )
