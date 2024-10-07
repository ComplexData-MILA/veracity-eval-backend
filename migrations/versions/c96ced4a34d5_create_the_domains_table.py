"""Create the domains table

Revision ID: c96ced4a34d5
Revises: 8e30e71f4a2f
Create Date: 2024-10-07 12:02:15.725741

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "c96ced4a34d5"
down_revision: Union[str, None] = "8e30e71f4a2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("domain_name", sa.String(), nullable=False),
        sa.Column("credibility_score", sa.Float(), nullable=False),
        sa.Column("is_reliable", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column(
            "updated_at", sa.TIMESTAMP(), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain_name"),
    )


def downgrade() -> None:
    op.drop_table("domains")
