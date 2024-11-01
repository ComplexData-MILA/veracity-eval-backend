"""update all timestamp columns to use timezones

Revision ID: 9492d0756e16
Revises: a35c37d7d3b7
Create Date: 2024-10-31 19:25:24.413980

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError


# revision identifiers, used by Alembic.
revision: str = "9492d0756e16"
down_revision: Union[str, None] = "a35c37d7d3b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def process_table_column(table: str, column: str, is_upgrade: bool = True) -> None:
    """Process a single column in a table with proper error handling."""
    try:
        with op.get_context().autocommit_block():
            if is_upgrade:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} "
                    f"TYPE TIMESTAMP WITH TIME ZONE "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
                print(f"Updated {table}.{column} to use timezone")
            else:
                op.execute(
                    f"ALTER TABLE {table} ALTER COLUMN {column} "
                    f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                    f"USING {column} AT TIME ZONE 'UTC'"
                )
                print(f"Reverted {table}.{column} to not use timezone")
    except ProgrammingError as e:
        if 'column "%s" does not exist' % column in str(e):
            print(f"Skipping {table}.{column}: Column does not exist")
        else:
            print(f"Error processing {table}.{column}: {str(e)}")
    except Exception as e:
        print(f"Error processing {table}.{column}: {str(e)}")


def upgrade() -> None:
    table_columns = {
        "users": ["created_at", "updated_at", "last_login"],
        "claims": ["created_at", "updated_at"],
        "analysis": ["created_at", "updated_at"],
        "sources": ["created_at", "updated_at"],
        "feedback": ["created_at", "updated_at"],
        "conversations": ["created_at", "updated_at", "start_time", "end_time"],
        "messages": ["created_at", "updated_at", "timestamp"],
        "domains": ["created_at", "updated_at"],
        "claim_conversations": ["created_at", "updated_at", "start_time", "end_time"],
    }

    # Process each table and column
    for table, columns in table_columns.items():
        for column in columns:
            process_table_column(table, column, True)


def downgrade() -> None:
    table_columns = {
        "users": ["created_at", "updated_at", "last_login"],
        "claims": ["created_at", "updated_at"],
        "analysis": ["created_at", "updated_at"],
        "sources": ["created_at", "updated_at"],
        "feedback": ["created_at", "updated_at"],
        "conversations": ["created_at", "updated_at", "start_time", "end_time"],
        "messages": ["created_at", "updated_at", "timestamp"],
        "domains": ["created_at", "updated_at"],
        "claim_conversations": ["created_at", "updated_at", "start_time", "end_time"],
    }

    # Process each table and column
    for table, columns in table_columns.items():
        for column in columns:
            process_table_column(table, column, False)
