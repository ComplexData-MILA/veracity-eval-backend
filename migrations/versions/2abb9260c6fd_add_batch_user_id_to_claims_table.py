"""Add batch_user_id to claims table

Revision ID: 2abb9260c6fd
Revises: b2122b621d0a
Create Date: 2025-04-10 21:03:31.820890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "2abb9260c6fd"
down_revision: Union[str, None] = "b2122b621d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("claims", sa.Column("batch_user_id", sa.Text(), nullable=True))
    # ### end Alembic commands ###

    op.execute(
        """
        CREATE TABLE social_media_clients (
        auth0_id VARCHAR PRIMARY KEY REFERENCES users(auth0_id),
        platform TEXT NOT NULL
        );
    """
    )

    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        VALUES ('I1eyLfAX26wlOMiY4n5SxWOsWrSNXLWU@clients', 'BlueSky');
    """
    )

    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        VALUES ('K46Fnu6E21BG0x3KfNknffbKdTbOHlzw@clients', 'X');
    """
    )

    op.execute(
        """
        INSERT INTO social_media_clients (auth0_id, platform)
        VALUES ('GbaexhSrWJnbX19M4HYuGH87ROyzwJne@clients', 'Reddit');
    """
    )


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("claims", "batch_user_id")
    # ### end Alembic commands ###

    op.execute(
        """
        DROP TABLE social_media_clients;
    """
    )
