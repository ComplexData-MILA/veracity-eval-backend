"""Create message types and status enums, add domain content tables

Revision ID: d331ddcf6fe8
Revises: 789b6e667dc6
Create Date: 2024-10-23 19:21:01.872795

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d331ddcf6fe8"
down_revision: Union[str, None] = "789b6e667dc6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums first
    op.execute("CREATE TYPE conversation_status AS ENUM ('active', 'paused', 'completed', 'archived')")
    op.execute("CREATE TYPE message_sender_type AS ENUM ('user', 'bot', 'system')")
    op.execute(
        "CREATE TYPE claim_status AS ENUM ('pending', 'analyzing', 'analyzed', 'disputed', 'verified', 'rejected')"
    )
    op.execute("CREATE TYPE analysis_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'disputed')")

    # Add new columns to users table
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
    op.create_index(op.f("ix_users_auth0_id"), "users", ["auth0_id"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Add status to claims table
    op.add_column(
        "claims",
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "analyzing", "analyzed", "disputed", "verified", "rejected", name="claim_status"
            ),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_index(op.f("ix_claims_status"), "claims", ["status"], unique=False)

    # Add status to analysis table
    op.add_column(
        "analysis",
        sa.Column(
            "status",
            postgresql.ENUM("pending", "processing", "completed", "failed", "disputed", name="analysis_status"),
            nullable=False,
            server_default="pending",
        ),
    )
    op.create_index(op.f("ix_analysis_status"), "analysis", ["status"], unique=False)

    # Add domain_id and content to sources table
    op.add_column("sources", sa.Column("domain_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("sources", sa.Column("content", sa.Text(), nullable=True))
    op.create_foreign_key(None, "sources", "domains", ["domain_id"], ["id"])
    op.create_index("idx_source_url_hash", "sources", [sa.text("md5(url)")], unique=True)

    # Convert conversations.status to enum type
    op.execute("ALTER TABLE conversations ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE conversations ALTER COLUMN status TYPE conversation_status USING status::conversation_status"
    )
    op.execute("ALTER TABLE conversations ALTER COLUMN status SET DEFAULT 'active'")
    op.create_index(op.f("ix_conversations_status"), "conversations", ["status"], unique=False)

    # Update messages table
    op.execute(
        "ALTER TABLE messages ALTER COLUMN sender_type TYPE message_sender_type USING sender_type::message_sender_type"
    )
    op.create_index(op.f("ix_messages_sender_type"), "messages", ["sender_type"], unique=False)
    op.create_index(
        "idx_message_conversation_timestamp", "messages", ["conversation_id", sa.text("timestamp DESC")], unique=False
    )
    op.create_index(
        "idx_message_claim_conversation_timestamp",
        "messages",
        ["claim_conversation_id", sa.text("timestamp DESC")],
        unique=False,
    )

    # Add updated_at column to all tables
    tables = ["users", "claims", "analysis", "sources", "feedback", "conversations", "messages", "claim_conversations"]
    for table in tables:
        op.add_column(table, sa.Column("updated_at", sa.TIMESTAMP(), nullable=False, server_default=sa.text("now()")))

    # ADD missing columns here 
    # Created_at is missing from sources
    # Created at is missing from conversations
    # Created at is missing from messages
    # Updated at is missing from claim conversations, DONE above
    # Created at is missing from claim conversations 

    tables = ["sources", "conversations", "messages", "claim_conversations"]
    for table in tables:
        op.add_column(table, sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=True))

def downgrade() -> None:
    #TODO take away the columns 

    # Remove indices
    op.drop_index("idx_message_claim_conversation_timestamp")
    op.drop_index("idx_message_conversation_timestamp")
    op.drop_index("idx_source_url_hash")
    op.drop_index("ix_messages_sender_type")
    op.drop_index("ix_conversations_status")
    op.drop_index("ix_analysis_status")
    op.drop_index("ix_claims_status")
    op.drop_index("ix_users_username")
    op.drop_index("ix_users_email")
    op.drop_index("ix_users_auth0_id")

    # Remove updated_at columns
    tables = ["users", "claims", "analysis", "sources", "feedback", "conversations", "messages"]
    for table in tables:
        op.drop_column(table, "updated_at")

    # Remove domain_id and content from sources
    op.drop_constraint(None, "sources", type_="foreignkey")
    op.drop_column("sources", "content")
    op.drop_column("sources", "domain_id")

    # Convert conversations.status back to string
    op.execute("ALTER TABLE conversations ALTER COLUMN status TYPE varchar USING status::varchar")
    op.execute("ALTER TABLE conversations ALTER COLUMN status SET DEFAULT 'active'")

    # Convert messages.sender_type back to string
    op.execute("ALTER TABLE messages ALTER COLUMN sender_type TYPE varchar USING sender_type::varchar")

    # Remove status columns from other tables
    op.drop_column("analysis", "status")
    op.drop_column("claims", "status")

    # Remove new user columns
    op.drop_column("users", "is_active")
    op.drop_column("users", "auth0_id")

    # Drop enums
    op.execute("DROP TYPE conversation_status")
    op.execute("DROP TYPE message_sender_type")
    op.execute("DROP TYPE claim_status")
    op.execute("DROP TYPE analysis_status")
