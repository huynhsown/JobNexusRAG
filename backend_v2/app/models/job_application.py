"""
Job application model for candidate -> job submissions.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ApplicationStatus(str, enum.Enum):
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"


class CvResolutionStatus(str, enum.Enum):
    RESOLVED = "resolved"
    SINGLE_CV_FALLBACK = "single_cv_fallback"
    SEARCHABLE_ONLY_FALLBACK = "searchable_only_fallback"
    PENDING_CV_RESOLUTION = "pending_cv_resolution"
    MISSING_CV_DATA = "missing_cv_data"


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("job_id", "candidate_id", name="uq_job_application_job_candidate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_application_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    candidate_cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_cvs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.APPLIED
    )
    cv_resolution_status: Mapped[CvResolutionStatus] = mapped_column(
        Enum(CvResolutionStatus, native_enum=False),
        default=CvResolutionStatus.PENDING_CV_RESOLUTION,
    )
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    job: Mapped["JobPosting"] = relationship(back_populates="applications")
    candidate: Mapped["Candidate"] = relationship(back_populates="applications")
    candidate_cv: Mapped["CandidateCV | None"] = relationship(back_populates="applications")
    matches: Mapped[list["MatchResult"]] = relationship(
        back_populates="application",
        foreign_keys="MatchResult.application_id",
    )
