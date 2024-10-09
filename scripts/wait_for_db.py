import time
import psycopg2
from app.core.config import settings


def wait_for_db():
    max_retries = 30
    retry_interval = 2

    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries} to connect to the database...")
            conn = psycopg2.connect(settings.get_database_url)
            conn.close()
            print("Successfully connected to the database!")
            return
        except psycopg2.OperationalError as e:
            print(f"Failed to connect to the database. Error: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
            else:
                print("Max retries reached. Could not connect to the database.")
        except Exception as e:
            print(f"Unexpected error occurred: {str(e)}")
            raise

    raise Exception("Could not connect to the database after multiple retries")


if __name__ == "__main__":
    wait_for_db()
