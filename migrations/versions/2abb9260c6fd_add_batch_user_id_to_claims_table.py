"""Add batch_user_id to claims table

Revision ID: 2abb9260c6fd
Revises: b2122b621d0a
Create Date: 2025-04-10 21:03:31.820890
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2abb9260c6fd"
down_revision: Union[str, None] = "b2122b621d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing migration: add the new column
    op.add_column("claims", sa.Column("batch_user_id", sa.Text(), nullable=True))

    # Existing migration: create the new table
    op.execute(
        """
        CREATE TABLE social_media_clients (
            auth0_id VARCHAR PRIMARY KEY REFERENCES users(auth0_id),
            platform TEXT NOT NULL
        );
        """
    )

    # The change makes the migration safe by preventing inserts into social_media_clients unless the referenced user already exists in users.

    # New: only insert BlueSky client if the matching user already exists
    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        SELECT 'I1eyLfAX26wlOMiY4n5SxWOsWrSNXLWU@clients', 'BlueSky'
        WHERE EXISTS (
            SELECT 1 FROM users
            WHERE auth0_id = 'I1eyLfAX26wlOMiY4n5SxWOsWrSNXLWU@clients'
        );
        """
    )

    # New: only insert X client if the matching user already exists
    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        SELECT 'K46Fnu6E21BG0x3KfNknffbKdTbOHlzw@clients', 'X'
        WHERE EXISTS (
            SELECT 1 FROM users
            WHERE auth0_id = 'K46Fnu6E21BG0x3KfNknffbKdTbOHlzw@clients'
        );
        """
    )

    # New: only insert Reddit client if the matching user already exists
    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        SELECT 'GbaexhSrWJnbX19M4HYuGH87ROyzwJne@clients', 'Reddit'
        WHERE EXISTS (
            SELECT 1 FROM users
            WHERE auth0_id = 'GbaexhSrWJnbX19M4HYuGH87ROyzwJne@clients'
        );
        """
    )


def downgrade() -> None:
    # Existing migration: drop the social_media_clients table
    op.execute(
        """
        DROP TABLE social_media_clients;
        """
    )

    # Existing migration: remove the batch_user_id column
    op.drop_column("claims", "batch_user_id")
