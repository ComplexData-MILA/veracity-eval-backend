import time
import psycopg2
from app.core.config import settings


def wait_for_db():
    max_retries = 30
    retry_interval = 2

    for _ in range(max_retries):
        try:
            conn = psycopg2.connect(settings.get_database_url)
            conn.close()
            print("Database is ready!")
            return
        except psycopg2.OperationalError:
            print("Waiting for database to be ready...")
            time.sleep(retry_interval)

    raise Exception("Could not connect to the database after multiple retries")


if __name__ == "__main__":
    wait_for_db()
