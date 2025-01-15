"""Update conversation and message structure for hierachical claims

Revision ID: 789b6e667dc6
Revises: c96ced4a34d5
Create Date: 2024-10-22 11:30:29.637344

"""

from typing import Sequence, Union
from sqlalchemy.dialects.postgresql import UUID
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "789b6e667dc6"
down_revision: Union[str, None] = "c96ced4a34d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create a temporary messages table to store existing data
    op.create_table(
        "messages_temp",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=True),
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("claim_id", UUID(), nullable=True),
        sa.Column("analysis_id", UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy existing data to temporary table
    op.execute(
        """
        INSERT INTO messages_temp (id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id)
        SELECT id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id
        FROM messages
        """
    )

    # Drop existing messages table with its constraints
    op.drop_table("messages")

    # Create new messages table with updated structure
    op.create_table(
        "messages",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=False),  # Now required
        sa.Column("claim_conversation_id", UUID(), nullable=True),  # New column
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("claim_id", UUID(), nullable=True),
        sa.Column("analysis_id", UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analysis.id"], ondelete="SET NULL"),
        sa.CheckConstraint("sender_type IN ('user', 'bot')"),
    )

    # Create claim_conversations table
    op.create_table(
        "claim_conversations",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=False),
        sa.Column("claim_id", UUID(), nullable=False),
        sa.Column("start_time", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('active', 'closed')"),
    )

    # Add foreign key for claim_conversation_id in messages
    op.create_foreign_key(
        "fk_messages_claim_conversation_id_claim_conversations",
        "messages",
        "claim_conversations",
        ["claim_conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Copy data back from temporary table
    op.execute(
        """
        INSERT INTO messages (id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id)
        SELECT id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id
        FROM messages_temp
        WHERE conversation_id IS NOT NULL
        """
    )

    # Drop temporary table
    op.drop_table("messages_temp")

    # Add indexes for better query performance
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_claim_conversation_id", "messages", ["claim_conversation_id"])
    op.create_index("ix_claim_conversations_conversation_id", "claim_conversations", ["conversation_id"])
    op.create_index("ix_claim_conversations_claim_id", "claim_conversations", ["claim_id"])


def downgrade() -> None:
    # First, create a temporary table to store existing data
    op.create_table(
        "messages_temp",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=True),
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("claim_id", UUID(), nullable=True),
        sa.Column("analysis_id", UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy existing data to temporary table
    op.execute(
        """
        INSERT INTO messages_temp (id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id)
        SELECT id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id
        FROM messages
        """
    )

    # Drop indexes
    op.drop_index("ix_messages_conversation_id")
    op.drop_index("ix_messages_claim_conversation_id")
    op.drop_index("ix_claim_conversations_conversation_id")
    op.drop_index("ix_claim_conversations_claim_id")

    # Drop tables
    op.drop_table("messages")
    op.drop_table("claim_conversations")

    # Recreate original messages table
    op.create_table(
        "messages",
        sa.Column("id", UUID(), nullable=False),
        sa.Column("conversation_id", UUID(), nullable=False),
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("claim_id", UUID(), nullable=True),
        sa.Column("analysis_id", UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["claims.id"],
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"],
            ["analysis.id"],
        ),
        sa.CheckConstraint("sender_type IN ('user', 'bot')"),
    )

    # Copy data back
    op.execute(
        """
        INSERT INTO messages (id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id)
        SELECT id, conversation_id, sender_type, content, timestamp, claim_id, analysis_id
        FROM messages_temp
        """
    )

    # Drop temporary table
    op.drop_table("messages_temp")
