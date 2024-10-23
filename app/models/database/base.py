from datetime import UTC, datetime
from typing import Any, Dict
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import UUID
import uuid

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",  # Index
    "uq": "uq_%(table_name)s_%(column_0_name)s",  # Unique constraint
    "ck": "ck_%(table_name)s_%(constraint_name)s",  # Check constraint
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",  # Foreign key
    "pk": "pk_%(table_name)s",  # Primary key
}


class Base(AsyncAttrs, DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    Features:
    - Automatic table naming
    - Common columns (id, created_at, updated_at)
    - JSON serialization
    - Async support
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case and pluralize
        name = cls.__name__.replace("Model", "")
        return "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_").lower() + "s"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, doc="Primary key using UUID4"
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, doc="Timestamp when the record was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        doc="Timestamp when the record was last updated",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result

    def __repr__(self) -> str:
        """String representation of the model."""
        values = ", ".join(f"{column.name}={getattr(self, column.name)!r}" for column in self.__table__.columns)
        return f"{self.__class__.__name__}({values})"


class TimestampMixin:
    """Mixin to add timestamp fields."""

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.now(UTC), nullable=False, doc="Timestamp when the record was created"
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(UTC),
        onupdate=datetime.now(UTC),
        nullable=False,
        doc="Timestamp when the record was last updated",
    )
