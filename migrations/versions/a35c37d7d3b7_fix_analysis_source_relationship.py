"""fix_analysis_source_relationship

Revision ID: a35c37d7d3b7
Revises: d331ddcf6fe8
Create Date: 2024-10-24 22:14:30.270657

"""

from typing import Sequence, Union
from sqlalchemy.dialects import postgresql
import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a35c37d7d3b7"
down_revision: Union[str, None] = "d331ddcf6fe8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    conn = op.get_bind()
    insp = inspect(conn)
    return table_name in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()

    # First check if we need to rename the table
    if table_exists("analysiss") and not table_exists("analysis"):
        op.execute("ALTER TABLE analysiss RENAME TO analysis")

    # If neither table exists, create the analysis table
    if not table_exists("analysis"):
        op.create_table(
            "analysis",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("claim_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("veracity_score", sa.Float(), nullable=False),
            sa.Column("confidence_score", sa.Float(), nullable=False),
            sa.Column("analysis_text", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

        # Add constraints after table creation
        op.create_foreign_key(
            "fk_analysis_claim_id_claims", "analysis", "claims", ["claim_id"], ["id"], ondelete="CASCADE"
        )

        op.create_check_constraint(
            "ck_analysis_veracity_score_range", "analysis", "veracity_score >= 0 AND veracity_score <= 1"
        )

        op.create_check_constraint(
            "ck_analysis_confidence_score_range", "analysis", "confidence_score >= 0 AND confidence_score <= 1"
        )

    if table_exists("sources"):
        insp = inspect(conn)
        constraints = insp.get_foreign_keys("sources")

        # Drop any existing analysis foreign key
        for constraint in constraints:
            if constraint["referred_table"] == "analysis":
                op.drop_constraint(constraint["name"], "sources", type_="foreignkey")

        op.create_foreign_key(
            "fk_sources_analysis_id_analysis", "sources", "analysis", ["analysis_id"], ["id"], ondelete="CASCADE"
        )

        try:
            op.create_check_constraint(
                "ck_sources_credibility_score_range", "sources", "credibility_score >= 0 AND credibility_score <= 1"
            )
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()

    if table_exists("sources"):
        # Remove constraints from sources
        insp = inspect(conn)
        constraints = insp.get_foreign_keys("sources")

        for constraint in constraints:
            if constraint["referred_table"] == "analysis":
                op.drop_constraint(constraint["name"], "sources", type_="foreignkey")

        try:
            op.drop_constraint("ck_sources_credibility_score_range", "sources", type_="check")
        except Exception:
            pass

    if table_exists("analysis"):
        # Drop analysis table and all its constraints
        op.drop_table("analysis")
