"""Add timestamps to sources table

Revision ID: de978baa01ff
Revises: 9492d0756e16
Create Date: 2024-11-03 19:53:50.089453

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "de978baa01ff"
down_revision: Union[str, None] = "9492d0756e16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # op.add_column(
    #     "sources",
    #     sa.Column(
    #         "created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
    #     ),
    # )

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
        CREATE TRIGGER update_sources_updated_at
            BEFORE UPDATE ON sources
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_sources_updated_at ON sources")

    # op.drop_column("sources", "created_at")
