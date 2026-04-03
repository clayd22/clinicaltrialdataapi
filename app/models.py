from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Trial(Base):
    __tablename__ = "trials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_id: Mapped[str] = mapped_column(String(50), nullable=False)
    registry_source: Mapped[str] = mapped_column(String(50), nullable=False)
    # Both titles may not be necessary for an absolute MVP, but including both
    # because the human-readable brief_title is really useful for consumers
    brief_title: Mapped[str | None] = mapped_column(Text)
    official_title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(50))
    phase: Mapped[str | None] = mapped_column(String(100))
    study_type: Mapped[str | None] = mapped_column(String(50))
    brief_summary: Mapped[str | None] = mapped_column(Text)
    conditions: Mapped[dict | None] = mapped_column(JSON)
    interventions: Mapped[dict | None] = mapped_column(JSON)
    primary_outcome: Mapped[dict | None] = mapped_column(JSON)
    eligibility_criteria: Mapped[str | None] = mapped_column(Text)
    locations: Mapped[dict | None] = mapped_column(JSON)
    sponsor: Mapped[str | None] = mapped_column(String(500))
    enrollment_count: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)
    harvested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_json: Mapped[dict | None] = mapped_column(JSON)

    __table_args__ = (
        UniqueConstraint("registry_source", "registry_id", name="uq_registry"),
        Index("ix_last_updated", "last_updated"),
        Index("ix_status", "status"),
        Index("ix_registry_source", "registry_source"),
    )
