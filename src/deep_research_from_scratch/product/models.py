"""SQLAlchemy models for the product-oriented copilot."""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from deep_research_from_scratch.product.db import Base


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def utc_hours_from_now(hours: int) -> datetime:
    """Return a timezone-aware timestamp in the future."""
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def generate_id() -> str:
    """Generate stable string identifiers."""
    return str(uuid4())


class WorkspaceRole(str, enum.Enum):
    owner = "owner"
    member = "member"


class InviteStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"
    expired = "expired"


class CopilotMode(str, enum.Enum):
    research = "research"
    learn = "learn"
    research_then_learn = "research_then_learn"


class RunStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ReportStatus(str, enum.Enum):
    draft = "draft"
    reviewed = "reviewed"
    final = "final"


class LearningSessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


class ReviewDecision(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class KnowledgeDocumentKind(str, enum.Enum):
    pdf = "pdf"
    markdown = "markdown"
    text = "text"
    url = "url"
    note = "note"


class KnowledgeDocumentStatus(str, enum.Enum):
    queued = "queued"
    ready = "ready"
    failed = "failed"


class BackgroundJobType(str, enum.Enum):
    ingest_document = "ingest_document"
    ingest_url = "ingest_url"
    export_report_markdown = "export_report_markdown"
    export_report_pdf = "export_report_pdf"
    export_learning_session_summary = "export_learning_session_summary"
    export_workspace_summary = "export_workspace_summary"


class BackgroundJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[WorkspaceRole] = mapped_column(default=WorkspaceRole.member, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[WorkspaceRole] = mapped_column(default=WorkspaceRole.member)
    invite_token: Mapped[str] = mapped_column(Text, unique=True, index=True)
    invited_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[InviteStatus] = mapped_column(default=InviteStatus.pending, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: utc_hours_from_now(72))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectRun(Base):
    __tablename__ = "project_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[CopilotMode] = mapped_column(index=True)
    status: Mapped[RunStatus] = mapped_column(default=RunStatus.queued, index=True)
    input_messages: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunReviewFlag(Base):
    __tablename__ = "run_review_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("project_runs.id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True, nullable=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("project_runs.id"), index=True, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    executive_summary: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[ReportStatus] = mapped_column(default=ReportStatus.draft, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportSection(Base):
    __tablename__ = "report_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    heading: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    citation_source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    excerpt: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceReview(Base):
    __tablename__ = "source_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    reviewer_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[ReviewDecision] = mapped_column(default=ReviewDecision.pending, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[LearningSessionStatus] = mapped_column(default=LearningSessionStatus.active, index=True)
    preferred_explanation_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_checkpoint_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    learning_session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str] = mapped_column(Text)
    study_material: Mapped[str] = mapped_column(Text)
    quiz_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    citation_source_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_answers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    simplified_material: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MasteryRecord(Base):
    __tablename__ = "mastery_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(255), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_state: Mapped[str] = mapped_column(String(50), default="review_now")
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    preferred_explanation_style: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_history: Mapped[list[float]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True, nullable=True)
    learning_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_sessions.id"),
        index=True,
        nullable=True,
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[KnowledgeDocumentKind] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[KnowledgeDocumentStatus] = mapped_column(default=KnowledgeDocumentStatus.queued, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), index=True, nullable=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("reports.id"), index=True, nullable=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_documents.id"), index=True, nullable=True)
    job_type: Mapped[BackgroundJobType] = mapped_column(index=True)
    status: Mapped[BackgroundJobStatus] = mapped_column(default=BackgroundJobStatus.pending, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
