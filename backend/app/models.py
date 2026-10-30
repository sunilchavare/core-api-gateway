from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class APIKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_value: Mapped[str] = mapped_column(unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(default=True)
    # Requests allowed per rate limit window (60 seconds).
    quota_limit: Mapped[int] = mapped_column(default=10)