"""Add numerical feedback labels

Revision ID: 158c26933ce4
Revises: af6e75192548
Create Date: 2025-01-14 14:09:14.702751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4 

# revision identifiers, used by Alembic.
revision: str = '158c26933ce4'
down_revision: Union[str, None] = 'af6e75192548'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feedback', sa.Column('labels', sa.ARRAY(sa.Integer()), nullable=True))
    # ### end Alembic commands ###

    op.create_table(
        "feedback_labels",
        sa.Column("label", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("label", "start_time"),
    )

    op.execute(
        """
        INSERT INTO feedback_labels (label, text, start_time, end_time)
        VALUES
            (0, 'Other', NOW(), NULL),
            (1, 'Lack of credible sources', NOW(), NULL),
            (2, 'Score contradicts my understanding', NOW(), NULL),
            (3, 'Explanation is too vague', NOW(), NULL),
            (4, 'Evidence is unclear or incomplete', NOW(), NULL),
            (5, 'Key details are missing', NOW(), NULL),
            (6, 'Design or Functionality', NOW(), NULL),
            (7, 'Some sources are unclear', NOW(), NULL),
            (8, 'Score is partially justified', NOW(), NULL),
            (9, 'Explanation lacks detail', NOW(), NULL),
            (10, 'Mixed or inconsistent information', NOW(), NULL),
            (11, 'Key details are missing', NOW(), NULL),
            (12, 'Design or Functionality', NOW(), NULL),
            (13, 'Sources are credible and reliable', NOW(), NULL),
            (14, 'Score is clear and justified', NOW(), NULL),
            (15, 'Explanation is well-supported', NOW(), NULL),
            (16, 'Aligns with my understanding', NOW(), NULL),
            (17, 'Key details are included', NOW(), NULL),
            (18, 'Design or Functionality', NOW(), NULL);
        """

    )



def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('feedback', 'labels')
    # ### end Alembic commands ###

    op.drop_table("feedback_labels")
