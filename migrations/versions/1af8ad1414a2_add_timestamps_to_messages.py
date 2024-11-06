"""Add timestamps to messages

Revision ID: 1af8ad1414a2
Revises: a482f7b0316a
Create Date: 2024-11-05 19:40:05.591915

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1af8ad1414a2"
down_revision: Union[str, None] = "a482f7b0316a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
    DO $$
    BEGIN
        BEGIN
            ALTER TABLE messages
            ADD COLUMN created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
        EXCEPTION
            WHEN duplicate_column THEN
                NULL;
        END;

        BEGIN
            ALTER TABLE messages
            ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP;
        EXCEPTION
            WHEN duplicate_column THEN
                NULL;
        END;
    END $$;
    """
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

    op.execute(
        """
    DROP TRIGGER IF EXISTS update_messages_updated_at ON messages;
    CREATE TRIGGER update_messages_updated_at
        BEFORE UPDATE ON messages
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_messages_updated_at ON messages")

    op.execute(
        """
    ALTER TABLE messages
    DROP COLUMN IF EXISTS updated_at,
    DROP COLUMN IF EXISTS created_at;
    """
    )
