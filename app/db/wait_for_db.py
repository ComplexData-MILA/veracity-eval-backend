import time
import os
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def wait_for_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    engine = create_engine(db_url)
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            engine.connect()
            print("Database is ready!")
            return
        except OperationalError:
            print(
                f"Database not ready. Waiting... (Attempt {attempt + 1}/{max_attempts})"
            )
            time.sleep(1)
    print("Could not connect to database.")
    exit(1)


if __name__ == "__main__":
    wait_for_db()
