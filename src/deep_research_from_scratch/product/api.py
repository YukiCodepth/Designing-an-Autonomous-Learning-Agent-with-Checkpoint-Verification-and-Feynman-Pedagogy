"""FastAPI application for the productized research and learning copilot."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from deep_research_from_scratch.product.auth import create_access_token, decode_access_token
from deep_research_from_scratch.product.config import settings
from deep_research_from_scratch.product.db import get_db
from deep_research_from_scratch.product.knowledge import ensure_product_dirs
from deep_research_from_scratch.product.models import BackgroundJob, BackgroundJobType, Project, User, Workspace
from deep_research_from_scratch.product.schemas import (
    ActivityItem,
    AnalyticsResponse,
    BackgroundJobResponse,
    CheckpointResponse,
    CheckpointSubmissionRequest,
    CheckpointSubmissionResponse,
    CommentCreate,
    CommentResponse,
    InviteAcceptRequest,
    KnowledgeDocumentResponse,
    KnowledgeNoteCreate,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchHit,
    KnowledgeUrlCreate,
    LaunchLearningRequest,
    LearningSessionResponse,
    LoginRequest,
    MasteryRecordResponse,
    ProjectCreate,
    ProjectDetailResponse,
    ProjectResponse,
    ProjectRunCreate,
    ProjectRunResponse,
    ReportResponse,
    ReportSectionResponse,
    ReportStatusUpdate,
    RunReviewFlagCreate,
    RunReviewFlagResponse,
    SourceResponse,
    SourceReviewCreate,
    SourceReviewResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceInviteCreate,
    WorkspaceInviteResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from deep_research_from_scratch.product.services import (
    accept_workspace_invite,
    authenticate_user,
    compare_project_runs,
    create_knowledge_note,
    create_learning_session_comment,
    create_project,
    create_report_comment,
    create_run_review_flag,
    create_source_review,
    create_workspace,
    create_workspace_invite,
    get_learning_session_bundle,
    get_report_bundle,
    get_user_workspaces,
    get_workspace_activity,
    get_workspace_analytics,
    launch_learning_session,
    list_learning_session_comments,
    list_project_knowledge_documents,
    list_project_reports,
    list_project_review_flags,
    list_project_runs,
    list_report_comments,
    list_source_reviews_for_report,
    list_workspace_invites,
    list_workspace_jobs,
    list_workspace_members,
    list_workspace_projects,
    queue_knowledge_document_upload,
    queue_knowledge_url_ingestion,
    queue_learning_session_export,
    queue_report_export,
    queue_workspace_export,
    require_workspace_access,
    register_user,
    run_copilot,
    search_project_knowledge_hits,
    submit_checkpoint_answers,
    update_report_status,
)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _serialize_user(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _serialize_workspace(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse.model_validate(workspace)


def _serialize_invite(invite) -> WorkspaceInviteResponse:
    return WorkspaceInviteResponse(
        **WorkspaceInviteResponse.model_validate(invite).model_dump(exclude={"invite_url"}),
        invite_url=f"{settings.app_base_url}/invites/{invite.invite_token}",
    )


def _serialize_report(report_id: str, user_id: str, db: Session) -> ReportResponse:
    report, sections, sources, source_reviews = get_report_bundle(db, user_id, report_id)
    return ReportResponse(
        **ReportResponse.model_validate(report).model_dump(
            exclude={"sections", "sources", "source_reviews"}
        ),
        sections=[ReportSectionResponse.model_validate(section) for section in sections],
        sources=[SourceResponse.model_validate(source) for source in sources],
        source_reviews=[SourceReviewResponse.model_validate(review) for review in source_reviews],
    )


def _serialize_learning_session(learning_session_id: str, user_id: str, db: Session) -> LearningSessionResponse:
    session_row, checkpoints, comments = get_learning_session_bundle(db, user_id, learning_session_id)
    return LearningSessionResponse(
        **LearningSessionResponse.model_validate(session_row).model_dump(exclude={"checkpoints", "comments"}),
        checkpoints=[CheckpointResponse.model_validate(checkpoint) for checkpoint in checkpoints],
        comments=[CommentResponse.model_validate(comment) for comment in comments],
    )


def _serialize_document_row(row: dict) -> KnowledgeDocumentResponse:
    document = row["document"]
    return KnowledgeDocumentResponse(
        **KnowledgeDocumentResponse.model_validate(document).model_dump(exclude={"chunk_count"}),
        chunk_count=row["chunk_count"],
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the bearer token."""
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Ensure local artifact directories exist."""
    ensure_product_dirs()


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health endpoint for product API consumers."""
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    """Readiness endpoint that verifies database connectivity."""
    db.execute(text("SELECT 1"))
    Path(settings.artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
    return {"status": "ready"}


@app.post("/auth/register", response_model=TokenResponse)
def register(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Register a new user and create a personal workspace."""
    user, workspace = register_user(db, payload)
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=_serialize_user(user),
        workspace=_serialize_workspace(workspace),
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Authenticate a user and return a bearer token."""
    user, workspace = authenticate_user(db, payload)
    token = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        user=_serialize_user(user),
        workspace=_serialize_workspace(workspace),
    )


@app.get("/auth/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    """Return the authenticated user."""
    return _serialize_user(current_user)


@app.post("/auth/accept-invite", response_model=WorkspaceInviteResponse)
def accept_invite(
    payload: InviteAcceptRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceInviteResponse:
    """Accept a workspace invitation."""
    invite = accept_workspace_invite(db, current_user.id, payload.token)
    return _serialize_invite(invite)


@app.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkspaceResponse]:
    """List workspaces for the current user."""
    return [WorkspaceResponse.model_validate(workspace) for workspace in get_user_workspaces(db, current_user.id)]


@app.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace_route(
    payload: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceResponse:
    """Create a new workspace."""
    workspace = create_workspace(db, current_user.id, payload)
    return WorkspaceResponse.model_validate(workspace)


@app.get("/workspaces/{workspace_id}", response_model=WorkspaceDetailResponse)
def workspace_detail(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceDetailResponse:
    """Return workspace details with members, projects, invites, and activity."""
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    members = list_workspace_members(db, current_user.id, workspace_id)
    projects = list_workspace_projects(db, current_user.id, workspace_id)
    invites = list_workspace_invites(db, current_user.id, workspace_id)
    activity = get_workspace_activity(db, current_user.id, workspace_id)
    return WorkspaceDetailResponse(
        workspace=WorkspaceResponse.model_validate(workspace),
        members=[WorkspaceMemberResponse.model_validate(member) for member in members],
        projects=[ProjectResponse.model_validate(project) for project in projects],
        pending_invites=[_serialize_invite(invite) for invite in invites if invite.status.value == "pending"],
        activity=[ActivityItem.model_validate(item) for item in activity],
    )


@app.get("/workspaces/{workspace_id}/activity", response_model=list[ActivityItem])
def workspace_activity(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ActivityItem]:
    """List the latest workspace activity items."""
    return [ActivityItem.model_validate(item) for item in get_workspace_activity(db, current_user.id, workspace_id)]


@app.get("/workspaces/{workspace_id}/invites", response_model=list[WorkspaceInviteResponse])
def workspace_invites(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[WorkspaceInviteResponse]:
    """List workspace invites."""
    return [_serialize_invite(invite) for invite in list_workspace_invites(db, current_user.id, workspace_id)]


@app.post("/workspaces/{workspace_id}/invites", response_model=WorkspaceInviteResponse)
def create_invite_route(
    workspace_id: str,
    payload: WorkspaceInviteCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkspaceInviteResponse:
    """Create a workspace invitation."""
    invite = create_workspace_invite(db, current_user.id, workspace_id, payload)
    return _serialize_invite(invite)


@app.get("/workspaces/{workspace_id}/jobs", response_model=list[BackgroundJobResponse])
def workspace_jobs(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[BackgroundJobResponse]:
    """List background jobs for a workspace."""
    return [BackgroundJobResponse.model_validate(job) for job in list_workspace_jobs(db, current_user.id, workspace_id)]


@app.get("/jobs/{job_id}", response_model=BackgroundJobResponse)
def get_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Fetch a single background job."""
    job = db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.workspace_id:
        require_workspace_access(db, current_user.id, job.workspace_id)
    return BackgroundJobResponse.model_validate(job)


@app.get("/jobs/{job_id}/artifact")
def download_job_artifact(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    """Download a completed job artifact."""
    job = db.get(BackgroundJob, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.workspace_id:
        require_workspace_access(db, current_user.id, job.workspace_id)
    if not job.artifact_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job artifact is not ready.")
    artifact_path = Path(job.artifact_path)
    if not artifact_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file not found.")
    return FileResponse(path=artifact_path, filename=artifact_path.name)


@app.post("/workspaces/{workspace_id}/exports/summary", response_model=BackgroundJobResponse)
def export_workspace_summary_route(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Queue a workspace summary export."""
    job = queue_workspace_export(db, current_user.id, workspace_id)
    return BackgroundJobResponse.model_validate(job)


@app.post("/projects", response_model=ProjectResponse)
def create_project_route(
    payload: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Create a new project."""
    project = create_project(db, current_user.id, payload)
    return ProjectResponse.model_validate(project)


@app.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectResponse]:
    """List projects in a workspace."""
    return [
        ProjectResponse.model_validate(project)
        for project in list_workspace_projects(db, current_user.id, workspace_id)
    ]


@app.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    """Fetch a single project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    list_workspace_projects(db, current_user.id, project.workspace_id)
    return ProjectResponse.model_validate(project)


@app.get("/projects/{project_id}/detail", response_model=ProjectDetailResponse)
def get_project_detail(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectDetailResponse:
    """Return an expanded project dashboard payload."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    runs = list_project_runs(db, current_user.id, project_id)
    reports = list_project_reports(db, current_user.id, project_id)
    documents = list_project_knowledge_documents(db, current_user.id, project_id)
    review_flags = list_project_review_flags(db, current_user.id, project_id)
    return ProjectDetailResponse(
        project=ProjectResponse.model_validate(project),
        runs=[ProjectRunResponse.model_validate(run) for run in runs],
        reports=[_serialize_report(report.id, current_user.id, db) for report in reports],
        knowledge_documents=[_serialize_document_row(row) for row in documents],
        review_flags=[RunReviewFlagResponse.model_validate(flag) for flag in review_flags],
    )


@app.get("/projects/{project_id}/reports", response_model=list[ReportResponse])
def project_reports(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ReportResponse]:
    """List reports saved for a project."""
    return [_serialize_report(report.id, current_user.id, db) for report in list_project_reports(db, current_user.id, project_id)]


@app.post("/projects/{project_id}/runs", response_model=ProjectRunResponse)
def create_run(
    project_id: str,
    payload: ProjectRunCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectRunResponse:
    """Run the unified copilot and persist the result."""
    run, report, learning_session = run_copilot(db, current_user.id, project_id, payload)
    return ProjectRunResponse(
        **ProjectRunResponse.model_validate(run).model_dump(exclude={"report", "learning_session"}),
        report=_serialize_report(report.id, current_user.id, db) if report else None,
        learning_session=_serialize_learning_session(learning_session.id, current_user.id, db)
        if learning_session
        else None,
    )


@app.get("/projects/{project_id}/runs", response_model=list[ProjectRunResponse])
def project_runs(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ProjectRunResponse]:
    """List historical runs for a project."""
    return [ProjectRunResponse.model_validate(run) for run in list_project_runs(db, current_user.id, project_id)]


@app.get("/projects/{project_id}/runs/compare")
def compare_runs(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """Compare recent runs for the same project."""
    return compare_project_runs(db, current_user.id, project_id)


@app.get("/projects/{project_id}/review-flags", response_model=list[RunReviewFlagResponse])
def project_review_flags(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[RunReviewFlagResponse]:
    """List review flags for a project."""
    return [
        RunReviewFlagResponse.model_validate(flag)
        for flag in list_project_review_flags(db, current_user.id, project_id)
    ]


@app.post("/runs/{run_id}/review-flags", response_model=RunReviewFlagResponse)
def add_run_review_flag(
    run_id: str,
    payload: RunReviewFlagCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RunReviewFlagResponse:
    """Create a review flag for a run."""
    flag = create_run_review_flag(db, current_user.id, run_id, payload)
    return RunReviewFlagResponse.model_validate(flag)


@app.get("/projects/{project_id}/knowledge/documents", response_model=list[KnowledgeDocumentResponse])
def list_knowledge_documents(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[KnowledgeDocumentResponse]:
    """List project knowledge documents."""
    return [_serialize_document_row(row) for row in list_project_knowledge_documents(db, current_user.id, project_id)]


@app.post("/projects/{project_id}/knowledge/documents", response_model=BackgroundJobResponse)
def upload_knowledge_document(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
) -> BackgroundJobResponse:
    """Upload a document and queue ingestion."""
    _, job = queue_knowledge_document_upload(db, current_user.id, project_id, file)
    return BackgroundJobResponse.model_validate(job)


@app.post("/projects/{project_id}/knowledge/urls", response_model=BackgroundJobResponse)
def queue_url_ingestion(
    project_id: str,
    payload: KnowledgeUrlCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Queue URL ingestion."""
    _, job = queue_knowledge_url_ingestion(db, current_user.id, project_id, payload)
    return BackgroundJobResponse.model_validate(job)


@app.post("/projects/{project_id}/knowledge/notes", response_model=KnowledgeDocumentResponse)
def create_note(
    project_id: str,
    payload: KnowledgeNoteCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeDocumentResponse:
    """Create and ingest a note immediately."""
    document = create_knowledge_note(db, current_user.id, project_id, payload)
    matching = next(
        (
            row
            for row in list_project_knowledge_documents(db, current_user.id, project_id)
            if row["document"].id == document.id
        ),
        {"document": document, "chunk_count": 0},
    )
    return _serialize_document_row(matching)


@app.post("/projects/{project_id}/knowledge/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    project_id: str,
    payload: KnowledgeSearchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeSearchResponse:
    """Search private project knowledge."""
    hits = search_project_knowledge_hits(db, current_user.id, project_id, payload)
    return KnowledgeSearchResponse(
        query=payload.query,
        hits=[
            KnowledgeSearchHit(
                document_id=hit["document_id"],
                document_title=hit["document_title"],
                chunk_id=hit["chunk_id"],
                content=hit["content"],
                score=hit["score"],
                metadata_json=hit["metadata_json"],
            )
            for hit in hits
        ],
    )


@app.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Return a full report with sources and sections."""
    return _serialize_report(report_id, current_user.id, db)


@app.get("/reports/{report_id}/sources", response_model=list[SourceResponse])
def get_report_sources(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SourceResponse]:
    """Return just the sources for a report."""
    _, _, sources, _ = get_report_bundle(db, current_user.id, report_id)
    return [SourceResponse.model_validate(source) for source in sources]


@app.post("/reports/{report_id}/status", response_model=ReportResponse)
def set_report_status(
    report_id: str,
    payload: ReportStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Update a report's review status."""
    report = update_report_status(db, current_user.id, report_id, payload.status)
    return _serialize_report(report.id, current_user.id, db)


@app.post("/reports/{report_id}/learn", response_model=LearningSessionResponse)
def learn_from_report(
    report_id: str,
    payload: LaunchLearningRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LearningSessionResponse:
    """Launch a learning session from a saved report."""
    learning_session = launch_learning_session(db, current_user.id, report_id, payload.learning_preferences)
    return _serialize_learning_session(learning_session.id, current_user.id, db)


@app.get("/reports/{report_id}/comments", response_model=list[CommentResponse])
def report_comments(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CommentResponse]:
    """List comments on a report."""
    return [CommentResponse.model_validate(comment) for comment in list_report_comments(db, current_user.id, report_id)]


@app.post("/reports/{report_id}/comments", response_model=CommentResponse)
def add_report_comment(
    report_id: str,
    payload: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CommentResponse:
    """Add a comment to a report."""
    comment = create_report_comment(db, current_user.id, report_id, payload)
    return CommentResponse.model_validate(comment)


@app.get("/reports/{report_id}/source-reviews", response_model=list[SourceReviewResponse])
def report_source_reviews(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[SourceReviewResponse]:
    """List source reviews for a report."""
    return [
        SourceReviewResponse.model_validate(review)
        for review in list_source_reviews_for_report(db, current_user.id, report_id)
    ]


@app.post("/reports/{report_id}/exports/markdown", response_model=BackgroundJobResponse)
def export_report_markdown_route(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Queue a markdown export for a report."""
    job = queue_report_export(db, current_user.id, report_id, export_type=BackgroundJobType.export_report_markdown)
    return BackgroundJobResponse.model_validate(job)


@app.post("/reports/{report_id}/exports/pdf", response_model=BackgroundJobResponse)
def export_report_pdf_route(
    report_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Queue a PDF export for a report."""
    job = queue_report_export(db, current_user.id, report_id, export_type=BackgroundJobType.export_report_pdf)
    return BackgroundJobResponse.model_validate(job)


@app.post("/sources/{source_id}/reviews", response_model=SourceReviewResponse)
def add_source_review(
    source_id: str,
    payload: SourceReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SourceReviewResponse:
    """Review an individual source."""
    review = create_source_review(db, current_user.id, source_id, payload)
    return SourceReviewResponse.model_validate(review)


@app.get("/learning-sessions/{learning_session_id}", response_model=LearningSessionResponse)
def get_learning_session(
    learning_session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> LearningSessionResponse:
    """Return a learning session and its checkpoints."""
    return _serialize_learning_session(learning_session_id, current_user.id, db)


@app.get("/learning-sessions/{learning_session_id}/comments", response_model=list[CommentResponse])
def learning_session_comments(
    learning_session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[CommentResponse]:
    """List comments on a learning session."""
    return [
        CommentResponse.model_validate(comment)
        for comment in list_learning_session_comments(db, current_user.id, learning_session_id)
    ]


@app.post("/learning-sessions/{learning_session_id}/comments", response_model=CommentResponse)
def add_learning_session_comment(
    learning_session_id: str,
    payload: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CommentResponse:
    """Add a comment to a learning session."""
    comment = create_learning_session_comment(db, current_user.id, learning_session_id, payload)
    return CommentResponse.model_validate(comment)


@app.post("/learning-sessions/{learning_session_id}/exports/summary", response_model=BackgroundJobResponse)
def export_learning_session_summary_route(
    learning_session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BackgroundJobResponse:
    """Queue a learning-session summary export."""
    job = queue_learning_session_export(db, current_user.id, learning_session_id)
    return BackgroundJobResponse.model_validate(job)


@app.post("/checkpoints/{checkpoint_id}/submit", response_model=CheckpointSubmissionResponse)
def submit_checkpoint(
    checkpoint_id: str,
    payload: CheckpointSubmissionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CheckpointSubmissionResponse:
    """Evaluate checkpoint answers and update mastery."""
    checkpoint, mastery, next_action = submit_checkpoint_answers(db, current_user.id, checkpoint_id, payload)
    return CheckpointSubmissionResponse(
        checkpoint=CheckpointResponse.model_validate(checkpoint),
        mastery_record=MasteryRecordResponse.model_validate(mastery),
        next_recommended_action=next_action,
    )


@app.get("/analytics/workspaces/{workspace_id}", response_model=AnalyticsResponse)
def workspace_analytics(
    workspace_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsResponse:
    """Return workspace analytics for dashboards."""
    return get_workspace_analytics(db, current_user.id, workspace_id)
