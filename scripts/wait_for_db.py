import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from app.core.config import settings
import sys
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_db_url(url: str) -> dict:
    """Parse database URL into connection parameters."""
    parsed = urlparse(url)
    return {
        "dbname": parsed.path[1:],
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port or 5432,
    }


def wait_for_db() -> None:
    """
    Wait for database to become available.
    Uses DATABASE_URL if available, falls back to individual parameters.
    """
    max_retries = 30
    initial_retry_interval = 1
    max_retry_interval = 10
    retry_interval = initial_retry_interval

    logger.info("Waiting for database to become available...")

    conn_params = {
        "connect_timeout": 3,
        "keepalives": 1,
        "keepalives_idle": 5,
        "keepalives_interval": 2,
        "keepalives_count": 3,
    }

    if settings.DATABASE_URL:
        logger.info("Using DATABASE_URL for connection")
        try:
            db_params = parse_db_url(settings.DATABASE_URL)
            conn_params.update(db_params)
        except Exception as e:
            logger.error(f"Failed to parse DATABASE_URL: {e}")
            sys.exit(1)
    else:
        logger.info("Using individual connection parameters")
        conn_params.update(
            {
                "dbname": settings.POSTGRES_DB,
                "user": settings.POSTGRES_USER,
                "password": settings.POSTGRES_PASSWORD,
                "host": settings.POSTGRES_HOST,
                "port": settings.POSTGRES_PORT,
            }
        )

    for attempt in range(max_retries):
        try:
            logger.info(f"\nAttempt {attempt + 1}/{max_retries} to connect to the database...")

            safe_params = {k: v for k, v in conn_params.items() if k != "password"}
            logger.info(f"Connection parameters: {safe_params}")

            conn = psycopg2.connect(**conn_params)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        version(),
                        (SELECT count(*) FROM pg_stat_activity)
                """
                )
                db, user, version, connections = cur.fetchone()

                logger.info("Database connection successful!")
                logger.info(f"Connected to: {db}")
                logger.info(f"As user: {user}")
                logger.info(f"PostgreSQL version: {version}")
                logger.info(f"Current connections: {connections}")

                # Additional connectivity test
                cur.execute("SELECT pg_is_in_recovery()")
                is_replica = cur.fetchone()[0]
                logger.info(f"Database is{'not' if not is_replica else ''} in recovery mode")

            conn.close()
            return

        except psycopg2.OperationalError as e:
            if attempt < max_retries - 1:
                logger.error(f"Failed to connect to the database. Error: {str(e)}")
                logger.info(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
                retry_interval = min(retry_interval * 2, max_retry_interval)
            else:
                logger.error("\nFatal: Could not connect to the database after maximum retries.")
                logger.error(f"Last error: {str(e)}")
                sys.exit(1)

        except Exception as e:
            logger.error(f"\nUnexpected error while connecting to database: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            sys.exit(1)

        finally:
            try:
                if "conn" in locals() and conn:
                    conn.close()
            except Exception:
                pass

    logger.error("\nFatal: Database connection attempts exhausted")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
