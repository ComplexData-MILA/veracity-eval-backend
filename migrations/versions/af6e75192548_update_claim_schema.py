"""update claim schema

Revision ID: af6e75192548
Revises: c50d4df9aeba
Create Date: 2024-12-16 10:15:50.112149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "af6e75192548"
down_revision: Union[str, None] = "c50d4df9aeba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column("analysis", "confidence_score", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=True)
    # op.alter_column('claims', 'context',
    #            existing_type=sa.TEXT(),
    #            nullable=True)
    op.alter_column("messages", "conversation_id", existing_type=sa.UUID(), nullable=True)
    # op.alter_column('sources', 'snippet',
    #            existing_type=sa.TEXT(),
    #            nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    # op.alter_column('sources', 'snippet',
    #            existing_type=sa.TEXT(),
    #            nullable=False)
    op.alter_column("messages", "conversation_id", existing_type=sa.UUID(), nullable=False)
    # op.alter_column('claims', 'context',
    #    existing_type=sa.TEXT(),
    #    nullable=False)
    op.alter_column("analysis", "confidence_score", existing_type=sa.DOUBLE_PRECISION(precision=53), nullable=False)
    # ### end Alembic commands ###
