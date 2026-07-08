"""
Matching/recommendation schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.match import MatchMode, MatchStatus


class MatchRequest(BaseModel):
    top_k: int = Field(default=10, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreBreakdown(BaseModel):
    semantic_score: float = 0.0
    skill_match_score: float = 0.0
    experience_score: float = 0.0
    location_score: float = 0.0
    salary_score: float = 0.0


class MatchExplanation(BaseModel):
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    related_skills_via_kg: list[str] = []
    experience_fit: str = ""
    salary_fit: str = ""
    location_fit: str = ""


class MatchResultResponse(BaseModel):
    id: int
    mode: MatchMode
    candidate_id: int
    source_candidate_id: int | None = None
    job_id: int
    candidate_cv_id: int | None = None
    application_id: int | None = None
    source_application_id: int | None = None
    overall_score: float
    scores: ScoreBreakdown
    matched_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    explanation: str | None = None
    status: MatchStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CandidateToJobsResponse(BaseModel):
    candidate_id: int
    source_candidate_id: int | None = None
    matches: list[MatchResultResponse]
    total: int


class JobToCandidatesResponse(BaseModel):
    job_id: int
    source_job_id: int | None = None
    matches: list[MatchResultResponse]
    total: int


class MatchExplainResponse(BaseModel):
    match_id: int
    mode: MatchMode
    candidate_id: int
    source_candidate_id: int | None = None
    job_id: int
    candidate_cv_id: int | None = None
    application_id: int | None = None
    source_application_id: int | None = None
    overall_score: float
    scores: ScoreBreakdown
    explanation: MatchExplanation
