"""Add timestamps to conversations

Revision ID: a482f7b0316a
Revises: de978baa01ff
Create Date: 2024-11-05 16:44:15.183217

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a482f7b0316a"
down_revision: Union[str, None] = "de978baa01ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(table: str, column: str) -> bool:
    inspector = sa.Inspector.from_engine(op.get_bind())
    return column in [c["name"] for c in inspector.get_columns(table)]


def upgrade() -> None:
    tables_to_check = ["conversations", "claim_conversations"]
    timestamp_columns = ["created_at", "updated_at", "start_time", "end_time"]

    for table in tables_to_check:
        for column in timestamp_columns:
            if column_exists(table, column):
                op.execute(
                    f"""
                    ALTER TABLE {table}
                    ALTER COLUMN {column} TYPE TIMESTAMP WITH TIME ZONE
                    USING {column} AT TIME ZONE 'UTC'
                """
                )
            else:
                op.add_column(
                    table,
                    sa.Column(
                        column, sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
                    ),
                )

    op.execute(
        """
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';
    """
    )

    for table in tables_to_check:
        trigger_name = f"update_{table}_updated_at"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
                BEFORE UPDATE ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """
        )


def downgrade() -> None:
    tables_to_check = ["conversations", "claim_conversations"]
    timestamp_columns = ["created_at", "updated_at", "start_time", "end_time"]

    for table in tables_to_check:
        for column in timestamp_columns:
            if column_exists(table, column):
                op.execute(
                    f"""
                    ALTER TABLE {table} 
                    ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE
                """
                )

    for table in tables_to_check:
        trigger_name = f"update_{table}_updated_at"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
