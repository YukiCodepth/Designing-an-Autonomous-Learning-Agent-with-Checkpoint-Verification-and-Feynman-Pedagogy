"""Pydantic schemas for the product API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from deep_research_from_scratch.product.models import (
    BackgroundJobStatus,
    BackgroundJobType,
    CopilotMode,
    InviteStatus,
    KnowledgeDocumentKind,
    KnowledgeDocumentStatus,
    LearningSessionStatus,
    ReportStatus,
    ReviewDecision,
    RunStatus,
    WorkspaceRole,
)


class ORMModel(BaseModel):
    """Shared base model with ORM serialization enabled."""

    model_config = ConfigDict(from_attributes=True)


class MessageInput(BaseModel):
    """Simple chat message passed to the copilot."""

    role: str = Field(default="user")
    content: str


class LearningPreferences(BaseModel):
    """Optional hints for learning session creation."""

    explanation_style: str | None = None
    difficulty: str | None = None
    focus_topics: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class InviteAcceptRequest(BaseModel):
    """Accept a workspace invite."""

    token: str


class UserResponse(ORMModel):
    """Public user view."""

    id: str
    email: EmailStr
    full_name: str
    created_at: datetime


class WorkspaceResponse(ORMModel):
    """Workspace view."""

    id: str
    name: str
    description: str | None
    created_by_user_id: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Auth response payload."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    workspace: WorkspaceResponse


class WorkspaceCreate(BaseModel):
    """Workspace creation payload."""

    name: str
    description: str | None = None


class WorkspaceMemberResponse(ORMModel):
    """Workspace membership view."""

    id: str
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    created_at: datetime


class WorkspaceInviteCreate(BaseModel):
    """Create a workspace invite."""

    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.member


class WorkspaceInviteResponse(ORMModel):
    """Workspace invite response payload."""

    id: str
    workspace_id: str
    email: EmailStr
    role: WorkspaceRole
    invite_token: str
    invited_by_user_id: str
    status: InviteStatus
    expires_at: datetime
    accepted_at: datetime | None
    created_at: datetime
    invite_url: str | None = None


class ProjectCreate(BaseModel):
    """Project creation payload."""

    workspace_id: str
    name: str
    description: str | None = None
    assigned_user_id: str | None = None


class ProjectResponse(ORMModel):
    """Project view."""

    id: str
    workspace_id: str
    name: str
    description: str | None
    created_by_user_id: str
    assigned_user_id: str | None
    created_at: datetime


class ProjectRunCreate(BaseModel):
    """Payload for running the unified copilot."""

    mode: CopilotMode
    messages: list[MessageInput]
    report_id: str | None = None
    learning_preferences: LearningPreferences | None = None


class SourceResponse(ORMModel):
    """Source payload returned with reports."""

    id: str
    url: str
    title: str
    excerpt: str
    summary: str
    published_at: str | None
    confidence: float
    metadata_json: dict[str, Any]
    created_at: datetime


class ReportSectionResponse(ORMModel):
    """Report section payload."""

    id: str
    heading: str
    body: str
    citation_source_ids: list[str]
    created_at: datetime


class SourceReviewCreate(BaseModel):
    """Review a source as part of HITL quality control."""

    decision: ReviewDecision
    note: str | None = None


class SourceReviewResponse(ORMModel):
    """Source review payload."""

    id: str
    source_id: str
    reviewer_user_id: str
    decision: ReviewDecision
    note: str | None
    created_at: datetime


class ReportStatusUpdate(BaseModel):
    """Update a report review state."""

    status: ReportStatus


class ReportResponse(ORMModel):
    """Detailed report response."""

    id: str
    workspace_id: str
    project_id: str
    run_id: str | None
    created_by_user_id: str
    title: str
    executive_summary: str
    body: str
    status: ReportStatus
    created_at: datetime
    sections: list[ReportSectionResponse] = Field(default_factory=list)
    sources: list[SourceResponse] = Field(default_factory=list)
    source_reviews: list[SourceReviewResponse] = Field(default_factory=list)


class CheckpointResponse(ORMModel):
    """Checkpoint response for learners."""

    id: str
    learning_session_id: str
    report_id: str
    title: str
    objective: str
    study_material: str
    quiz_questions: list[str]
    citation_source_ids: list[str]
    order_index: int
    score: int | None
    passed: bool | None
    feedback: str | None
    last_answers: list[str] | None
    simplified_material: str | None
    created_at: datetime
    updated_at: datetime


class LearningSessionResponse(ORMModel):
    """Learning session payload."""

    id: str
    workspace_id: str
    project_id: str
    report_id: str
    user_id: str
    status: LearningSessionStatus
    preferred_explanation_style: str | None
    current_checkpoint_index: int
    created_at: datetime
    updated_at: datetime
    checkpoints: list[CheckpointResponse] = Field(default_factory=list)
    comments: list["CommentResponse"] = Field(default_factory=list)


class MasteryRecordResponse(ORMModel):
    """Mastery state for a topic."""

    id: str
    workspace_id: str
    project_id: str
    user_id: str
    topic: str
    confidence: float
    last_reviewed_at: datetime | None
    next_review_at: datetime | None
    review_state: str
    failed_attempts: int
    preferred_explanation_style: str | None
    mastered: bool
    confidence_history: list[float]
    created_at: datetime
    updated_at: datetime


class ProjectRunResponse(ORMModel):
    """Stored project run payload."""

    id: str
    workspace_id: str
    project_id: str
    user_id: str
    mode: CopilotMode
    status: RunStatus
    input_messages: list[dict[str, str]]
    response_payload: dict[str, Any]
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    report: ReportResponse | None = None
    learning_session: LearningSessionResponse | None = None


class RunReviewFlagCreate(BaseModel):
    """Flag a run or report for human review."""

    severity: str = "medium"
    note: str
    report_id: str | None = None


class RunReviewFlagResponse(ORMModel):
    """Human-in-the-loop review flag payload."""

    id: str
    workspace_id: str
    project_id: str
    run_id: str
    report_id: str | None
    reviewer_user_id: str
    severity: str
    note: str
    created_at: datetime


class CommentCreate(BaseModel):
    """New comment payload."""

    body: str
    anchor: str | None = None


class CommentResponse(ORMModel):
    """Comment response."""

    id: str
    workspace_id: str
    project_id: str
    report_id: str | None
    learning_session_id: str | None
    user_id: str
    body: str
    anchor: str | None
    created_at: datetime


class LaunchLearningRequest(BaseModel):
    """Launch a learning session from a report."""

    learning_preferences: LearningPreferences | None = None


class CheckpointSubmissionRequest(BaseModel):
    """Submit answers for a checkpoint."""

    answers: list[str] = Field(min_length=1)
    preferred_explanation_style: str | None = None


class CheckpointSubmissionResponse(BaseModel):
    """Result of checkpoint evaluation."""

    checkpoint: CheckpointResponse
    mastery_record: MasteryRecordResponse
    next_recommended_action: str


class KnowledgeNoteCreate(BaseModel):
    """Create a text or markdown knowledge note."""

    title: str
    content: str
    kind: KnowledgeDocumentKind = KnowledgeDocumentKind.note
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class KnowledgeUrlCreate(BaseModel):
    """Queue a URL for ingestion."""

    url: str
    title: str | None = None


class KnowledgeDocumentResponse(ORMModel):
    """Knowledge document payload."""

    id: str
    workspace_id: str
    project_id: str
    created_by_user_id: str
    kind: KnowledgeDocumentKind
    title: str
    source_uri: str | None
    metadata_json: dict[str, Any]
    status: KnowledgeDocumentStatus
    created_at: datetime
    chunk_count: int = 0


class KnowledgeSearchRequest(BaseModel):
    """Search private workspace knowledge."""

    query: str
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchHit(BaseModel):
    """A single knowledge-search hit."""

    document_id: str
    document_title: str
    chunk_id: str
    content: str
    score: float
    metadata_json: dict[str, Any]


class KnowledgeSearchResponse(BaseModel):
    """Search response for project knowledge."""

    query: str
    hits: list[KnowledgeSearchHit]


class BackgroundJobResponse(ORMModel):
    """Background job payload."""

    id: str
    workspace_id: str | None
    project_id: str | None
    user_id: str | None
    report_id: str | None
    document_id: str | None
    job_type: BackgroundJobType
    status: BackgroundJobStatus
    payload: dict[str, Any]
    result_payload: dict[str, Any]
    artifact_path: str | None
    error_message: str | None
    run_after: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ActivityItem(BaseModel):
    """Workspace activity feed item."""

    kind: str
    entity_id: str
    title: str
    created_at: datetime


class ProjectDetailResponse(BaseModel):
    """Expanded project payload for dashboards."""

    project: ProjectResponse
    runs: list[ProjectRunResponse]
    reports: list[ReportResponse]
    knowledge_documents: list[KnowledgeDocumentResponse]
    review_flags: list[RunReviewFlagResponse]


class WorkspaceDetailResponse(BaseModel):
    """Expanded workspace payload."""

    workspace: WorkspaceResponse
    members: list[WorkspaceMemberResponse]
    projects: list[ProjectResponse]
    pending_invites: list[WorkspaceInviteResponse]
    activity: list[ActivityItem]


class AnalyticsResponse(BaseModel):
    """Workspace-level product analytics."""

    workspace_id: str
    total_projects: int
    total_runs: int
    total_reports: int
    total_learning_sessions: int
    total_comments: int
    total_knowledge_documents: int
    total_jobs: int
    checkpoint_pass_rate: float
    mastery_by_topic: list[dict[str, Any]]
    run_volume_by_project: list[dict[str, Any]]
    report_status_breakdown: list[dict[str, Any]]
    source_quality: list[dict[str, Any]]
    activity_counts: dict[str, int]


LearningSessionResponse.model_rebuild()
