"""Domain credibility made nullable

Revision ID: 87d9d7477f9c
Revises: 929c947e8f33
Create Date: 2025-01-21 18:42:42.847176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "87d9d7477f9c"
down_revision: Union[str, None] = "929c947e8f33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("domains", "credibility_score", existing_type=sa.Float, nullable=True)

    op.execute(
        """
        UPDATE domains
        SET credibility_score = NULL
        WHERE credibility_score = 0.5
    """
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###

    op.execute(
        """
        UPDATE domains
        SET credibility_score = 0.5
        WHERE credibility_score is NULL
    """
    )

    op.alter_column("domains", "credibility_score", existing_type=sa.Float, nullable=False)
    # ### end Alembic commands ###
