"""Add embedding field to Claim model

Revision ID: c705bfe3c5ed
Revises: 4bd2e2c4bc6c
Create Date: 2025-02-20 20:24:14.562605

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c705bfe3c5ed"
down_revision: Union[str, None] = "4bd2e2c4bc6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("claims", sa.Column("embedding", sa.ARRAY(sa.DOUBLE_PRECISION()), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("claims", "embedding")
    # ### end Alembic commands ###
