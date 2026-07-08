"""
MatchResult model — stores computed job-candidate matches with score breakdown.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MatchStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class MatchMode(str, enum.Enum):
    CANDIDATE_FIND_JOBS = "candidate_find_jobs"
    JOB_FIND_TALENT = "job_find_talent"
    JOB_RANK_APPLICANTS = "job_rank_applicants"


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), index=True
    )
    candidate_cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidate_cvs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_applications.id", ondelete="SET NULL"), index=True, nullable=True
    )
    mode: Mapped[MatchMode] = mapped_column(
        Enum(MatchMode, native_enum=False), default=MatchMode.CANDIDATE_FIND_JOBS
    )

    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    skill_match_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    salary_score: Mapped[float] = mapped_column(Float, default=0.0)

    matched_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    missing_skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), default=MatchStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    candidate: Mapped["Candidate"] = relationship(
        back_populates="matches", foreign_keys=[candidate_id]
    )
    job: Mapped["JobPosting"] = relationship(
        back_populates="matches", foreign_keys=[job_id]
    )
    candidate_cv: Mapped["CandidateCV | None"] = relationship(
        back_populates="matches",
        foreign_keys=[candidate_cv_id],
    )
    application: Mapped["JobApplication | None"] = relationship(
        back_populates="matches",
        foreign_keys=[application_id],
    )
