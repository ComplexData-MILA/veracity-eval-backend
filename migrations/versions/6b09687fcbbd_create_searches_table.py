"""Empty migration script

Revision ID: 6b09687fcbbd
Revises: 87d9d7477f9c
Create Date: 2025-01-23 15:22:28.897965

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b09687fcbbd'
down_revision: Union[str, None] = '87d9d7477f9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'searches',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        # Add other columns as needed
    )


def downgrade() -> None:
    op.drop_table('searches')
