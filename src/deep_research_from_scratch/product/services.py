"""Business logic for the product API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from deep_research_from_scratch.copilot_v2 import copilot_v2
from deep_research_from_scratch.product.auth import (
    create_invite_token,
    decode_invite_token,
    hash_password,
    verify_password,
)
from deep_research_from_scratch.product.config import settings
from deep_research_from_scratch.product.knowledge import (
    ensure_product_dirs,
    guess_document_kind,
    search_project_knowledge,
    upsert_document_chunks,
)
from deep_research_from_scratch.product.models import (
    BackgroundJob,
    BackgroundJobStatus,
    BackgroundJobType,
    Checkpoint,
    Comment,
    CopilotMode,
    InviteStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentKind,
    KnowledgeDocumentStatus,
    LearningSession,
    LearningSessionStatus,
    MasteryRecord,
    Project,
    ProjectRun,
    Report,
    ReportSection,
    ReportStatus,
    RunReviewFlag,
    RunStatus,
    Source,
    SourceReview,
    User,
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    WorkspaceRole,
)
from deep_research_from_scratch.product.schemas import (
    AnalyticsResponse,
    CheckpointSubmissionRequest,
    CommentCreate,
    KnowledgeNoteCreate,
    KnowledgeSearchRequest,
    KnowledgeUrlCreate,
    LearningPreferences,
    LoginRequest,
    MessageInput,
    ProjectCreate,
    ProjectRunCreate,
    RunReviewFlagCreate,
    SourceReviewCreate,
    UserCreate,
    WorkspaceCreate,
    WorkspaceInviteCreate,
)


evaluation_model = init_chat_model("google_genai:models/gemini-2.5-flash-lite", max_retries=0)


class EvaluationResult(BaseModel):
    """Structured scoring output for checkpoint submissions."""

    score: int = Field(ge=0, le=100)
    passed: bool
    feedback: str
    simplified_material: str
    next_recommended_action: str
    review_state: str = "review_now"


evaluation_structured_model = evaluation_model.with_structured_output(EvaluationResult)


def _fallback_evaluation_result(
    checkpoint: Checkpoint,
    payload: CheckpointSubmissionRequest,
) -> EvaluationResult:
    """Deterministic checkpoint scoring when the model is unavailable."""
    answers = [answer.strip() for answer in payload.answers if answer.strip()]
    avg_length = sum(len(answer) for answer in answers) / len(answers) if answers else 0
    score = 40
    if answers:
        score += min(30, len(answers) * 10)
    if avg_length >= 40:
        score += 20
    elif avg_length >= 20:
        score += 10
    keyword_boost = 0
    checkpoint_keywords = {
        token.lower()
        for token in checkpoint.title.replace("-", " ").split()
        if len(token) > 4
    }
    joined_answers = " ".join(answers).lower()
    if checkpoint_keywords and any(token in joined_answers for token in checkpoint_keywords):
        keyword_boost = 10
    score = min(100, score + keyword_boost)
    passed = score >= 70
    review_state = "mastered" if score >= 85 else "review_later" if passed else "review_now"
    feedback = (
        "Fallback evaluation used because the live model was unavailable. "
        "Your answers show the right direction, but you should tighten the explanation with one concrete example."
        if passed
        else "Fallback evaluation used because the live model was unavailable. Review the checkpoint material and answer each question with more concrete detail."
    )
    simplified_material = (
        checkpoint.simplified_material
        or checkpoint.study_material[:600]
        or "Explain the concept in plain language and connect it to one practical use case."
    )
    next_action = (
        "Move to the next checkpoint and revisit this topic later for spaced review."
        if passed
        else "Retry this checkpoint after reviewing the simplified material."
    )
    return EvaluationResult(
        score=score,
        passed=passed,
        feedback=feedback,
        simplified_material=simplified_material,
        next_recommended_action=next_action,
        review_state=review_state,
    )


def register_user(db: Session, payload: UserCreate) -> tuple[User, Workspace]:
    """Create a user and a personal workspace."""
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    workspace = Workspace(
        name=f"{payload.full_name}'s Workspace",
        description="Personal workspace created during signup.",
        created_by_user_id=user.id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role=WorkspaceRole.owner,
        )
    )
    db.commit()
    db.refresh(user)
    db.refresh(workspace)
    return user, workspace


def authenticate_user(db: Session, payload: LoginRequest) -> tuple[User, Workspace]:
    """Validate login credentials and return the default workspace."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    membership = db.scalar(
        select(WorkspaceMember)
        .where(WorkspaceMember.user_id == user.id)
        .order_by(WorkspaceMember.created_at.asc())
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No workspace found for user.")

    workspace = db.get(Workspace, membership.workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace no longer exists.")
    return user, workspace


def get_user_workspaces(db: Session, user_id: str) -> list[Workspace]:
    """List workspaces visible to the current user."""
    memberships = db.scalars(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
    ).all()
    workspace_ids = [membership.workspace_id for membership in memberships]
    if not workspace_ids:
        return []
    return db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids))).all()


def require_workspace_access(db: Session, user_id: str, workspace_id: str) -> WorkspaceMember:
    """Ensure the current user belongs to the workspace."""
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace access denied.")
    return membership


def require_workspace_owner(db: Session, user_id: str, workspace_id: str) -> WorkspaceMember:
    """Ensure the current user owns the workspace."""
    membership = require_workspace_access(db, user_id, workspace_id)
    if membership.role != WorkspaceRole.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required.")
    return membership


def require_project_access(db: Session, user_id: str, project_id: str) -> Project:
    """Ensure the current user can access the project."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    require_workspace_access(db, user_id, project.workspace_id)
    return project


def create_workspace(db: Session, user_id: str, payload: WorkspaceCreate) -> Workspace:
    """Create a new collaborative workspace."""
    workspace = Workspace(
        name=payload.name,
        description=payload.description,
        created_by_user_id=user_id,
    )
    db.add(workspace)
    db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceRole.owner,
        )
    )
    db.commit()
    db.refresh(workspace)
    return workspace


def list_workspace_members(db: Session, user_id: str, workspace_id: str) -> list[WorkspaceMember]:
    """List workspace memberships."""
    require_workspace_access(db, user_id, workspace_id)
    return db.scalars(
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    ).all()


def _invite_url(invite_token: str) -> str:
    return f"{settings.app_base_url}/invites/{invite_token}"


def create_workspace_invite(
    db: Session,
    user_id: str,
    workspace_id: str,
    payload: WorkspaceInviteCreate,
) -> WorkspaceInvite:
    """Create a workspace invite and persist its signed token."""
    require_workspace_owner(db, user_id, workspace_id)
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found.")

    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        existing_membership = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == existing_user.id,
            )
        )
        if existing_membership:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already belongs to this workspace.")

    token = create_invite_token(
        workspace_id=workspace_id,
        email=str(payload.email),
        role=payload.role.value,
    )
    invite = WorkspaceInvite(
        workspace_id=workspace_id,
        email=str(payload.email),
        role=payload.role,
        invite_token=token,
        invited_by_user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.invite_expire_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def list_workspace_invites(db: Session, user_id: str, workspace_id: str) -> list[WorkspaceInvite]:
    """List workspace invites."""
    require_workspace_access(db, user_id, workspace_id)
    return db.scalars(
        select(WorkspaceInvite)
        .where(WorkspaceInvite.workspace_id == workspace_id)
        .order_by(WorkspaceInvite.created_at.desc())
    ).all()


def accept_workspace_invite(db: Session, user_id: str, token: str) -> WorkspaceInvite:
    """Accept a signed workspace invite."""
    invite = db.scalar(select(WorkspaceInvite).where(WorkspaceInvite.invite_token == token))
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    payload = decode_invite_token(token)
    if not payload:
        invite.status = InviteStatus.expired
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token is invalid or expired.")

    user = db.get(User, user_id)
    if not user or user.email.lower() != invite.email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invite email does not match current user.")

    if invite.status == InviteStatus.revoked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has been revoked.")
    if invite.expires_at <= datetime.now(timezone.utc):
        invite.status = InviteStatus.expired
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has expired.")

    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invite.workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not membership:
        db.add(
            WorkspaceMember(
                workspace_id=invite.workspace_id,
                user_id=user_id,
                role=invite.role,
            )
        )
    invite.status = InviteStatus.accepted
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invite)
    return invite


def create_project(db: Session, user_id: str, payload: ProjectCreate) -> Project:
    """Create a project within a workspace."""
    require_workspace_access(db, user_id, payload.workspace_id)
    project = Project(
        workspace_id=payload.workspace_id,
        name=payload.name,
        description=payload.description,
        created_by_user_id=user_id,
        assigned_user_id=payload.assigned_user_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def list_workspace_projects(db: Session, user_id: str, workspace_id: str) -> list[Project]:
    """List projects in a workspace."""
    require_workspace_access(db, user_id, workspace_id)
    return db.scalars(
        select(Project)
        .where(Project.workspace_id == workspace_id)
        .order_by(Project.created_at.desc())
    ).all()


def queue_background_job(
    db: Session,
    *,
    job_type: BackgroundJobType,
    workspace_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
    report_id: str | None = None,
    document_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> BackgroundJob:
    """Persist a new background job."""
    job = BackgroundJob(
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        report_id=report_id,
        document_id=document_id,
        job_type=job_type,
        status=BackgroundJobStatus.pending,
        payload=payload or {},
    )
    db.add(job)
    db.flush()
    return job


def list_workspace_jobs(db: Session, user_id: str, workspace_id: str) -> list[BackgroundJob]:
    """List recent background jobs for a workspace."""
    require_workspace_access(db, user_id, workspace_id)
    return db.scalars(
        select(BackgroundJob)
        .where(BackgroundJob.workspace_id == workspace_id)
        .order_by(BackgroundJob.created_at.desc())
    ).all()


def _checkpoint_payload_to_rows(
    db: Session,
    report: Report,
    learning_session: LearningSession,
    checkpoints: list[dict[str, Any]],
) -> None:
    for checkpoint in checkpoints:
        db.add(
            Checkpoint(
                learning_session_id=learning_session.id,
                report_id=report.id,
                title=checkpoint["title"],
                objective=checkpoint["objective"],
                study_material=checkpoint["study_material"],
                quiz_questions=checkpoint["quiz_questions"],
                citation_source_ids=checkpoint.get("citation_source_ids", []),
                order_index=checkpoint.get("order_index", 0),
            )
        )
    db.flush()


def _create_learning_session(
    db: Session,
    user_id: str,
    workspace_id: str,
    project_id: str,
    report: Report,
    checkpoint_payload: list[dict[str, Any]],
    learning_preferences: LearningPreferences | None,
) -> LearningSession:
    style = learning_preferences.explanation_style if learning_preferences else None
    session = LearningSession(
        workspace_id=workspace_id,
        project_id=project_id,
        report_id=report.id,
        user_id=user_id,
        preferred_explanation_style=style,
        status=LearningSessionStatus.active,
    )
    db.add(session)
    db.flush()
    _checkpoint_payload_to_rows(db, report, session, checkpoint_payload)
    return session


def _persist_report_bundle(
    db: Session,
    user_id: str,
    workspace_id: str,
    project: Project,
    run: ProjectRun,
    result: dict[str, Any],
) -> Report | None:
    report_body = result.get("report_body", "")
    report_title = result.get("report_title", "")
    if not report_body and not report_title:
        return None

    report = Report(
        workspace_id=workspace_id,
        project_id=project.id,
        run_id=run.id,
        created_by_user_id=user_id,
        title=report_title or f"{project.name} report",
        executive_summary=result.get("report_summary", ""),
        body=report_body,
        status=ReportStatus.draft,
    )
    db.add(report)
    db.flush()

    source_id_lookup: dict[str, str] = {}
    for source in result.get("sources", []):
        source_row = Source(
            workspace_id=workspace_id,
            project_id=project.id,
            report_id=report.id,
            url=source["url"],
            title=source["title"],
            excerpt=source["excerpt"],
            summary=source["summary"],
            published_at=source.get("published_at"),
            confidence=float(source.get("confidence") or 0.0),
            metadata_json={
                "retrieved_at": source.get("retrieved_at"),
                "source_key": source.get("source_id"),
                "source_type": source.get("metadata_json", {}).get("kind", "web")
                if isinstance(source.get("metadata_json"), dict)
                else "web",
            },
        )
        db.add(source_row)
        db.flush()
        source_id_lookup[source["source_id"]] = source_row.id

    for order_index, section in enumerate(result.get("cited_sections", [])):
        db.add(
            ReportSection(
                report_id=report.id,
                heading=section["heading"],
                body=section["body"],
                citation_source_ids=[
                    source_id_lookup[citation["source_id"]]
                    for citation in section.get("citations", [])
                    if citation["source_id"] in source_id_lookup
                ],
                order_index=order_index,
            )
        )

    return report


def _build_copilot_context(
    db: Session,
    *,
    project: Project,
    messages: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Gather private knowledge and prior conclusions for research modes."""
    latest_question = next(
        (
            message["content"]
            for message in reversed(messages)
            if message.get("content")
        ),
        project.name,
    )
    hits = search_project_knowledge(db, project_id=project.id, query=latest_question, limit=5)
    prior_reports = db.scalars(
        select(Report)
        .where(Report.project_id == project.id)
        .order_by(Report.created_at.desc())
        .limit(3)
    ).all()
    for report in prior_reports:
        hits.append(
            {
                "document_id": report.id,
                "document_title": report.title,
                "chunk_id": f"report-summary-{report.id}",
                "content": report.executive_summary,
                "score": 0.82,
                "metadata_json": {"kind": "prior_report", "status": report.status.value},
                "source_id": f"prior-report-{report.id}",
                "url": f"workspace://reports/{report.id}",
                "title": report.title,
                "excerpt": report.executive_summary[:320],
                "summary": report.executive_summary[:480],
                "published_at": None,
                "confidence": 0.82,
                "retrieved_at": "prior-report",
            }
        )
    return hits[:8]


def run_copilot(
    db: Session,
    user_id: str,
    project_id: str,
    payload: ProjectRunCreate,
) -> tuple[ProjectRun, Report | None, LearningSession | None]:
    """Execute the unified graph and persist product-layer objects."""
    project = require_project_access(db, user_id, project_id)
    messages = [message.model_dump() for message in payload.messages]
    source_report = None

    run = ProjectRun(
        workspace_id=project.workspace_id,
        project_id=project.id,
        user_id=user_id,
        mode=payload.mode,
        status=RunStatus.running,
        input_messages=messages,
    )
    db.add(run)
    db.flush()

    report_body = None
    if payload.report_id:
        source_report = db.get(Report, payload.report_id)
        if not source_report or source_report.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found for project.")
        report_body = source_report.body

    knowledge_hits: list[dict[str, Any]] = []
    if payload.mode in {CopilotMode.research, CopilotMode.research_then_learn}:
        knowledge_hits = _build_copilot_context(db, project=project, messages=messages)

    graph_input: dict[str, Any] = {
        "workspace_id": project.workspace_id,
        "project_id": project.id,
        "mode": payload.mode.value,
        "messages": messages,
        "knowledge_hits": knowledge_hits,
        "learning_preferences": payload.learning_preferences.model_dump() if payload.learning_preferences else {},
    }
    if payload.report_id:
        graph_input["report_id"] = payload.report_id
    if report_body:
        graph_input["report_body"] = report_body

    try:
        result = copilot_v2.invoke(graph_input)
        run.status = RunStatus.completed
        run.response_payload = result
        run.completed_at = datetime.now(timezone.utc)
    except Exception as exc:  # pragma: no cover
        run.status = RunStatus.failed
        run.error_message = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise

    if payload.mode == CopilotMode.learn and source_report:
        report_row = source_report
    else:
        report_row = _persist_report_bundle(db, user_id, project.workspace_id, project, run, result)

    learning_session = None
    if report_row and result.get("checkpoint_list"):
        learning_session = _create_learning_session(
            db,
            user_id,
            project.workspace_id,
            project.id,
            report_row,
            result["checkpoint_list"],
            payload.learning_preferences,
        )

    db.commit()
    db.refresh(run)
    if report_row:
        db.refresh(report_row)
    if learning_session:
        db.refresh(learning_session)
    return run, report_row, learning_session


def launch_learning_session(
    db: Session,
    user_id: str,
    report_id: str,
    preferences: LearningPreferences | None,
) -> LearningSession:
    """Start a learning session from an existing report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)

    run_payload = ProjectRunCreate(
        mode=CopilotMode.learn,
        messages=[MessageInput(content=report.body)],
        report_id=report.id,
        learning_preferences=preferences,
    )
    _, _, learning_session = run_copilot(db, user_id, report.project_id, run_payload)
    if not learning_session:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create learning session.")
    return learning_session


def get_report_bundle(
    db: Session,
    user_id: str,
    report_id: str,
) -> tuple[Report, list[ReportSection], list[Source], list[SourceReview]]:
    """Fetch a report with its sections, sources, and source reviews."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)
    sections = db.scalars(
        select(ReportSection)
        .where(ReportSection.report_id == report_id)
        .order_by(ReportSection.created_at.asc())
    ).all()
    sources = db.scalars(select(Source).where(Source.report_id == report_id)).all()
    source_ids = [source.id for source in sources]
    reviews = db.scalars(
        select(SourceReview)
        .where(SourceReview.source_id.in_(source_ids or [""]))
        .order_by(SourceReview.created_at.desc())
    ).all()
    return report, sections, sources, reviews


def get_learning_session_bundle(
    db: Session,
    user_id: str,
    learning_session_id: str,
) -> tuple[LearningSession, list[Checkpoint], list[Comment]]:
    """Fetch a learning session, checkpoints, and comments."""
    session = db.get(LearningSession, learning_session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found.")
    require_workspace_access(db, user_id, session.workspace_id)
    checkpoints = db.scalars(
        select(Checkpoint)
        .where(Checkpoint.learning_session_id == learning_session_id)
        .order_by(Checkpoint.order_index.asc())
    ).all()
    comments = db.scalars(
        select(Comment)
        .where(Comment.learning_session_id == learning_session_id)
        .order_by(Comment.created_at.asc())
    ).all()
    return session, checkpoints, comments


def submit_checkpoint_answers(
    db: Session,
    user_id: str,
    checkpoint_id: str,
    payload: CheckpointSubmissionRequest,
) -> tuple[Checkpoint, MasteryRecord, str]:
    """Evaluate a checkpoint submission and update mastery."""
    checkpoint = db.get(Checkpoint, checkpoint_id)
    if not checkpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkpoint not found.")

    session = db.get(LearningSession, checkpoint.learning_session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found.")
    require_workspace_access(db, user_id, session.workspace_id)

    prompt = f"""
You are grading a learning checkpoint submission for an AI copilot product.

Checkpoint title: {checkpoint.title}
Objective: {checkpoint.objective}
Study material: {checkpoint.study_material}
Questions: {checkpoint.quiz_questions}
Learner answers: {payload.answers}
Preferred explanation style: {payload.preferred_explanation_style or session.preferred_explanation_style or 'plain_language'}

Rules:
- Score from 0 to 100.
- Pass only if the learner shows meaningful understanding.
- Give answer-level actionable feedback in one compact response.
- Provide a simplified explanation when the learner needs help.
- Recommend the next action.
- Return review_state as one of review_now, review_later, mastered.
"""
    try:
        result = evaluation_structured_model.invoke([HumanMessage(content=prompt)])
    except Exception:
        result = _fallback_evaluation_result(checkpoint, payload)

    checkpoint.last_answers = payload.answers
    checkpoint.score = result.score
    checkpoint.passed = result.passed
    checkpoint.feedback = result.feedback
    checkpoint.simplified_material = result.simplified_material

    checkpoints = db.scalars(
        select(Checkpoint)
        .where(Checkpoint.learning_session_id == session.id)
        .order_by(Checkpoint.order_index.asc())
    ).all()
    if result.passed:
        session.current_checkpoint_index = max(session.current_checkpoint_index, checkpoint.order_index + 1)
        if session.current_checkpoint_index >= len(checkpoints):
            session.status = LearningSessionStatus.completed

    mastery = db.scalar(
        select(MasteryRecord).where(
            MasteryRecord.workspace_id == session.workspace_id,
            MasteryRecord.project_id == session.project_id,
            MasteryRecord.user_id == user_id,
            MasteryRecord.topic == checkpoint.title,
        )
    )
    if not mastery:
        mastery = MasteryRecord(
            workspace_id=session.workspace_id,
            project_id=session.project_id,
            user_id=user_id,
            topic=checkpoint.title,
            preferred_explanation_style=payload.preferred_explanation_style or session.preferred_explanation_style,
        )
        db.add(mastery)

    now = datetime.now(timezone.utc)
    mastery.last_reviewed_at = now
    mastery.preferred_explanation_style = payload.preferred_explanation_style or session.preferred_explanation_style
    mastery.confidence = max(result.score / 100.0, 0.0)
    mastery.mastered = result.passed and result.score >= 85
    mastery.review_state = "mastered" if mastery.mastered else result.review_state
    mastery.next_review_at = now + timedelta(days=7 if mastery.mastered else 1)
    mastery.confidence_history = list(mastery.confidence_history or [])
    mastery.confidence_history.append(mastery.confidence)
    if result.passed:
        mastery.failed_attempts = mastery.failed_attempts
    else:
        mastery.failed_attempts += 1

    db.commit()
    db.refresh(checkpoint)
    db.refresh(mastery)
    return checkpoint, mastery, result.next_recommended_action


def list_project_runs(db: Session, user_id: str, project_id: str) -> list[ProjectRun]:
    """List saved runs for a project."""
    project = require_project_access(db, user_id, project_id)
    return db.scalars(
        select(ProjectRun)
        .where(ProjectRun.project_id == project.id)
        .order_by(ProjectRun.created_at.desc())
    ).all()


def list_project_reports(db: Session, user_id: str, project_id: str) -> list[Report]:
    """List saved reports for a project."""
    project = require_project_access(db, user_id, project_id)
    return db.scalars(
        select(Report)
        .where(Report.project_id == project.id)
        .order_by(Report.created_at.desc())
    ).all()


def create_report_comment(db: Session, user_id: str, report_id: str, payload: CommentCreate) -> Comment:
    """Add a comment to a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)
    comment = Comment(
        workspace_id=report.workspace_id,
        project_id=report.project_id,
        report_id=report.id,
        user_id=user_id,
        body=payload.body,
        anchor=payload.anchor,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def create_learning_session_comment(
    db: Session,
    user_id: str,
    learning_session_id: str,
    payload: CommentCreate,
) -> Comment:
    """Add a comment to a learning session."""
    session = db.get(LearningSession, learning_session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found.")
    require_workspace_access(db, user_id, session.workspace_id)
    comment = Comment(
        workspace_id=session.workspace_id,
        project_id=session.project_id,
        learning_session_id=session.id,
        user_id=user_id,
        body=payload.body,
        anchor=payload.anchor,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_report_comments(db: Session, user_id: str, report_id: str) -> list[Comment]:
    """List comments attached to a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)
    return db.scalars(
        select(Comment)
        .where(Comment.report_id == report.id)
        .order_by(Comment.created_at.asc())
    ).all()


def list_learning_session_comments(
    db: Session,
    user_id: str,
    learning_session_id: str,
) -> list[Comment]:
    """List comments attached to a learning session."""
    session = db.get(LearningSession, learning_session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found.")
    require_workspace_access(db, user_id, session.workspace_id)
    return db.scalars(
        select(Comment)
        .where(Comment.learning_session_id == session.id)
        .order_by(Comment.created_at.asc())
    ).all()


def update_report_status(db: Session, user_id: str, report_id: str, status_value: ReportStatus) -> Report:
    """Update report review state."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)
    report.status = status_value
    db.commit()
    db.refresh(report)
    return report


def create_run_review_flag(
    db: Session,
    user_id: str,
    run_id: str,
    payload: RunReviewFlagCreate,
) -> RunReviewFlag:
    """Flag a run or report for human review."""
    run = db.get(ProjectRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    require_workspace_access(db, user_id, run.workspace_id)
    flag = RunReviewFlag(
        workspace_id=run.workspace_id,
        project_id=run.project_id,
        run_id=run.id,
        report_id=payload.report_id,
        reviewer_user_id=user_id,
        severity=payload.severity,
        note=payload.note,
    )
    db.add(flag)
    db.commit()
    db.refresh(flag)
    return flag


def list_project_review_flags(db: Session, user_id: str, project_id: str) -> list[RunReviewFlag]:
    """List review flags for a project."""
    project = require_project_access(db, user_id, project_id)
    return db.scalars(
        select(RunReviewFlag)
        .where(RunReviewFlag.project_id == project.id)
        .order_by(RunReviewFlag.created_at.desc())
    ).all()


def create_source_review(
    db: Session,
    user_id: str,
    source_id: str,
    payload: SourceReviewCreate,
) -> SourceReview:
    """Review a source quality decision."""
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    require_workspace_access(db, user_id, source.workspace_id)
    review = SourceReview(
        source_id=source.id,
        reviewer_user_id=user_id,
        decision=payload.decision,
        note=payload.note,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def list_source_reviews_for_report(db: Session, user_id: str, report_id: str) -> list[SourceReview]:
    """List source reviews associated with a report."""
    report, _, sources, _ = get_report_bundle(db, user_id, report_id)
    source_ids = [source.id for source in sources]
    if not source_ids:
        return []
    return db.scalars(
        select(SourceReview)
        .where(SourceReview.source_id.in_(source_ids))
        .order_by(SourceReview.created_at.desc())
    ).all()


def create_knowledge_note(
    db: Session,
    user_id: str,
    project_id: str,
    payload: KnowledgeNoteCreate,
) -> KnowledgeDocument:
    """Create a workspace note and ingest it immediately."""
    project = require_project_access(db, user_id, project_id)
    document = KnowledgeDocument(
        workspace_id=project.workspace_id,
        project_id=project.id,
        created_by_user_id=user_id,
        kind=payload.kind,
        title=payload.title,
        source_uri=f"workspace://notes/{project.id}/{payload.title.lower().replace(' ', '-')}",
        content_text=payload.content,
        metadata_json=payload.metadata_json,
        status=KnowledgeDocumentStatus.queued,
    )
    db.add(document)
    db.flush()
    upsert_document_chunks(db, document, content_text=payload.content, metadata_json=payload.metadata_json)
    db.commit()
    db.refresh(document)
    return document


def queue_knowledge_url_ingestion(
    db: Session,
    user_id: str,
    project_id: str,
    payload: KnowledgeUrlCreate,
) -> tuple[KnowledgeDocument, BackgroundJob]:
    """Queue a URL for asynchronous ingestion."""
    project = require_project_access(db, user_id, project_id)
    document = KnowledgeDocument(
        workspace_id=project.workspace_id,
        project_id=project.id,
        created_by_user_id=user_id,
        kind=KnowledgeDocumentKind.url,
        title=payload.title or payload.url,
        source_uri=payload.url,
        content_text="",
        metadata_json={"source": "url"},
        status=KnowledgeDocumentStatus.queued,
    )
    db.add(document)
    db.flush()
    job = queue_background_job(
        db,
        job_type=BackgroundJobType.ingest_url,
        workspace_id=project.workspace_id,
        project_id=project.id,
        user_id=user_id,
        document_id=document.id,
        payload={"document_id": document.id},
    )
    db.commit()
    db.refresh(document)
    db.refresh(job)
    return document, job


def queue_knowledge_document_upload(
    db: Session,
    user_id: str,
    project_id: str,
    upload: UploadFile,
) -> tuple[KnowledgeDocument, BackgroundJob]:
    """Save an uploaded file and queue ingestion."""
    project = require_project_access(db, user_id, project_id)
    ensure_product_dirs()
    uploads_dir = Path(settings.uploads_dir) / project.id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = upload.filename or "uploaded.txt"
    target_path = uploads_dir / filename
    target_path.write_bytes(upload.file.read())
    kind = guess_document_kind(filename)

    document = KnowledgeDocument(
        workspace_id=project.workspace_id,
        project_id=project.id,
        created_by_user_id=user_id,
        kind=kind,
        title=filename,
        source_uri=str(target_path),
        content_text="",
        metadata_json={"source": "upload", "filename": filename},
        status=KnowledgeDocumentStatus.queued,
    )
    db.add(document)
    db.flush()
    job = queue_background_job(
        db,
        job_type=BackgroundJobType.ingest_document,
        workspace_id=project.workspace_id,
        project_id=project.id,
        user_id=user_id,
        document_id=document.id,
        payload={"document_id": document.id},
    )
    db.commit()
    db.refresh(document)
    db.refresh(job)
    return document, job


def list_project_knowledge_documents(
    db: Session,
    user_id: str,
    project_id: str,
) -> list[dict[str, Any]]:
    """List project knowledge documents with chunk counts."""
    project = require_project_access(db, user_id, project_id)
    documents = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.project_id == project.id)
        .order_by(KnowledgeDocument.created_at.desc())
    ).all()
    results: list[dict[str, Any]] = []
    for document in documents:
        chunk_count = len(
            db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id)).all()
        )
        results.append({"document": document, "chunk_count": chunk_count})
    return results


def search_project_knowledge_hits(
    db: Session,
    user_id: str,
    project_id: str,
    payload: KnowledgeSearchRequest,
) -> list[dict[str, Any]]:
    """Search a project's private knowledge base."""
    require_project_access(db, user_id, project_id)
    return search_project_knowledge(db, project_id=project_id, query=payload.query, limit=payload.limit)


def queue_report_export(
    db: Session,
    user_id: str,
    report_id: str,
    *,
    export_type: BackgroundJobType,
) -> BackgroundJob:
    """Queue markdown or PDF export for a report."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    require_workspace_access(db, user_id, report.workspace_id)
    job = queue_background_job(
        db,
        job_type=export_type,
        workspace_id=report.workspace_id,
        project_id=report.project_id,
        user_id=user_id,
        report_id=report.id,
        payload={"report_id": report.id},
    )
    db.commit()
    db.refresh(job)
    return job


def queue_learning_session_export(db: Session, user_id: str, learning_session_id: str) -> BackgroundJob:
    """Queue a learning-session summary export."""
    session = db.get(LearningSession, learning_session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning session not found.")
    require_workspace_access(db, user_id, session.workspace_id)
    job = queue_background_job(
        db,
        job_type=BackgroundJobType.export_learning_session_summary,
        workspace_id=session.workspace_id,
        project_id=session.project_id,
        user_id=user_id,
        payload={"learning_session_id": session.id},
    )
    db.commit()
    db.refresh(job)
    return job


def queue_workspace_export(db: Session, user_id: str, workspace_id: str) -> BackgroundJob:
    """Queue a workspace summary export."""
    require_workspace_access(db, user_id, workspace_id)
    job = queue_background_job(
        db,
        job_type=BackgroundJobType.export_workspace_summary,
        workspace_id=workspace_id,
        user_id=user_id,
        payload={"workspace_id": workspace_id},
    )
    db.commit()
    db.refresh(job)
    return job


def compare_project_runs(db: Session, user_id: str, project_id: str) -> list[dict[str, Any]]:
    """Return a simple comparison view of recent runs."""
    runs = list_project_runs(db, user_id, project_id)[:5]
    comparison: list[dict[str, Any]] = []
    for run in runs:
        comparison.append(
            {
                "run_id": run.id,
                "mode": run.mode.value,
                "status": run.status.value,
                "created_at": run.created_at,
                "report_title": run.response_payload.get("report_title") if run.response_payload else None,
                "source_count": len(run.response_payload.get("sources", [])) if run.response_payload else 0,
            }
        )
    return comparison


def get_workspace_activity(db: Session, user_id: str, workspace_id: str) -> list[dict[str, Any]]:
    """Build a workspace activity feed from key product objects."""
    require_workspace_access(db, user_id, workspace_id)
    runs = db.scalars(
        select(ProjectRun)
        .where(ProjectRun.workspace_id == workspace_id)
        .order_by(ProjectRun.created_at.desc())
        .limit(8)
    ).all()
    reports = db.scalars(
        select(Report)
        .where(Report.workspace_id == workspace_id)
        .order_by(Report.created_at.desc())
        .limit(8)
    ).all()
    comments = db.scalars(
        select(Comment)
        .where(Comment.workspace_id == workspace_id)
        .order_by(Comment.created_at.desc())
        .limit(8)
    ).all()
    documents = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.workspace_id == workspace_id)
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(8)
    ).all()
    jobs = db.scalars(
        select(BackgroundJob)
        .where(BackgroundJob.workspace_id == workspace_id)
        .order_by(BackgroundJob.created_at.desc())
        .limit(8)
    ).all()

    activity = [
        {"kind": "run", "entity_id": run.id, "title": f"{run.mode.value} run", "created_at": run.created_at}
        for run in runs
    ]
    activity.extend(
        {"kind": "report", "entity_id": report.id, "title": report.title, "created_at": report.created_at}
        for report in reports
    )
    activity.extend(
        {"kind": "comment", "entity_id": comment.id, "title": comment.body[:80], "created_at": comment.created_at}
        for comment in comments
    )
    activity.extend(
        {"kind": "knowledge", "entity_id": doc.id, "title": doc.title, "created_at": doc.created_at}
        for doc in documents
    )
    activity.extend(
        {
            "kind": "job",
            "entity_id": job.id,
            "title": f"{job.job_type.value} {job.status.value}",
            "created_at": job.created_at,
        }
        for job in jobs
    )
    return sorted(activity, key=lambda item: item["created_at"], reverse=True)[:20]


def get_workspace_analytics(db: Session, user_id: str, workspace_id: str) -> AnalyticsResponse:
    """Compute workspace analytics for dashboards."""
    require_workspace_access(db, user_id, workspace_id)

    projects = db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all()
    runs = db.scalars(select(ProjectRun).where(ProjectRun.workspace_id == workspace_id)).all()
    reports = db.scalars(select(Report).where(Report.workspace_id == workspace_id)).all()
    sessions = db.scalars(select(LearningSession).where(LearningSession.workspace_id == workspace_id)).all()
    comments = db.scalars(select(Comment).where(Comment.workspace_id == workspace_id)).all()
    documents = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == workspace_id)).all()
    jobs = db.scalars(select(BackgroundJob).where(BackgroundJob.workspace_id == workspace_id)).all()
    source_rows = db.scalars(select(Source).where(Source.workspace_id == workspace_id)).all()
    mastery = db.scalars(select(MasteryRecord).where(MasteryRecord.workspace_id == workspace_id)).all()
    checkpoints = db.scalars(
        select(Checkpoint).where(Checkpoint.learning_session_id.in_([session.id for session in sessions] or [""]))
    ).all()

    graded = [checkpoint for checkpoint in checkpoints if checkpoint.passed is not None]
    checkpoint_pass_rate = (
        len([checkpoint for checkpoint in graded if checkpoint.passed]) / len(graded)
        if graded
        else 0.0
    )

    run_volume_by_project = [
        {
            "project_id": project.id,
            "project_name": project.name,
            "run_count": len([run for run in runs if run.project_id == project.id]),
        }
        for project in projects
    ]
    report_status_breakdown = [
        {
            "status": status_value.value,
            "count": len([report for report in reports if report.status == status_value]),
        }
        for status_value in ReportStatus
    ]
    source_quality = [
        {
            "title": source.title,
            "confidence": source.confidence,
            "url": source.url,
        }
        for source in sorted(source_rows, key=lambda item: item.confidence, reverse=True)[:10]
    ]
    mastery_by_topic = [
        {
            "topic": record.topic,
            "confidence": record.confidence,
            "failed_attempts": record.failed_attempts,
            "mastered": record.mastered,
            "next_review_at": record.next_review_at,
        }
        for record in mastery
    ]
    activity_counts = {
        "runs": len(runs),
        "reports": len(reports),
        "learning_sessions": len(sessions),
        "comments": len(comments),
        "knowledge_documents": len(documents),
        "jobs": len(jobs),
    }

    return AnalyticsResponse(
        workspace_id=workspace_id,
        total_projects=len(projects),
        total_runs=len(runs),
        total_reports=len(reports),
        total_learning_sessions=len(sessions),
        total_comments=len(comments),
        total_knowledge_documents=len(documents),
        total_jobs=len(jobs),
        checkpoint_pass_rate=checkpoint_pass_rate,
        mastery_by_topic=mastery_by_topic,
        run_volume_by_project=run_volume_by_project,
        report_status_breakdown=report_status_breakdown,
        source_quality=source_quality,
        activity_counts=activity_counts,
    )
