"""Artifact exporters for reports, sessions, and workspace summaries."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from deep_research_from_scratch.product.config import settings
from deep_research_from_scratch.product.models import (
    Checkpoint,
    Comment,
    LearningSession,
    Project,
    Report,
    ReportSection,
)


def _artifact_path(*parts: str, suffix: str) -> Path:
    directory = Path(settings.artifacts_dir).joinpath(*parts[:-1])
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{parts[-1]}{suffix}"


def export_report_markdown(db: Session, report_id: str) -> str:
    """Write a report to a markdown artifact and return its path."""
    report = db.get(Report, report_id)
    if not report:
        raise ValueError("Report not found for export.")
    sections = db.scalars(
        select(ReportSection)
        .where(ReportSection.report_id == report.id)
        .order_by(ReportSection.order_index.asc())
    ).all()

    chunks = [f"# {report.title}", "", "## Executive Summary", report.executive_summary, ""]
    for section in sections:
        chunks.extend([f"## {section.heading}", section.body, ""])
    path = _artifact_path("reports", report.id, suffix=".md")
    path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
    return str(path)


def export_report_pdf(db: Session, report_id: str) -> str:
    """Render a report into a simple PDF artifact."""
    report = db.get(Report, report_id)
    if not report:
        raise ValueError("Report not found for export.")
    sections = db.scalars(
        select(ReportSection)
        .where(ReportSection.report_id == report.id)
        .order_by(ReportSection.order_index.asc())
    ).all()

    path = _artifact_path("reports", report.id, suffix=".pdf")
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = height - 48

    def draw_paragraph(text: str, *, font: str = "Helvetica", size: int = 11) -> None:
        nonlocal y
        pdf.setFont(font, size)
        for line in wrap(text, 94):
            if y < 48:
                pdf.showPage()
                pdf.setFont(font, size)
                y = height - 48
            pdf.drawString(44, y, line)
            y -= size + 4
        y -= 8

    draw_paragraph(report.title, font="Helvetica-Bold", size=18)
    draw_paragraph("Executive Summary", font="Helvetica-Bold", size=13)
    draw_paragraph(report.executive_summary)
    for section in sections:
        draw_paragraph(section.heading, font="Helvetica-Bold", size=13)
        draw_paragraph(section.body)
    pdf.save()
    return str(path)


def export_learning_session_summary(db: Session, learning_session_id: str) -> str:
    """Export a learning-session summary as markdown."""
    session = db.get(LearningSession, learning_session_id)
    if not session:
        raise ValueError("Learning session not found for export.")
    checkpoints = db.scalars(
        select(Checkpoint)
        .where(Checkpoint.learning_session_id == session.id)
        .order_by(Checkpoint.order_index.asc())
    ).all()

    chunks = [
        f"# Learning Session {session.id}",
        "",
        f"- Status: {session.status.value}",
        f"- Current checkpoint index: {session.current_checkpoint_index}",
        "",
    ]
    for checkpoint in checkpoints:
        chunks.extend(
            [
                f"## {checkpoint.order_index + 1}. {checkpoint.title}",
                checkpoint.study_material,
                "",
                f"Score: {checkpoint.score if checkpoint.score is not None else 'Not graded'}",
                f"Passed: {checkpoint.passed if checkpoint.passed is not None else 'Pending'}",
                checkpoint.feedback or "",
                "",
            ]
        )
    path = _artifact_path("learning_sessions", session.id, suffix=".md")
    path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
    return str(path)


def export_workspace_summary(db: Session, workspace_id: str) -> str:
    """Export a compact workspace summary for mentors or managers."""
    projects = db.scalars(select(Project).where(Project.workspace_id == workspace_id)).all()
    reports = db.scalars(select(Report).where(Report.workspace_id == workspace_id)).all()
    sessions = db.scalars(select(LearningSession).where(LearningSession.workspace_id == workspace_id)).all()
    comments = db.scalars(select(Comment).where(Comment.workspace_id == workspace_id)).all()

    lines = [
        f"# Workspace Summary {workspace_id}",
        "",
        f"- Projects: {len(projects)}",
        f"- Reports: {len(reports)}",
        f"- Learning Sessions: {len(sessions)}",
        f"- Comments: {len(comments)}",
        "",
        "## Projects",
    ]
    for project in projects:
        lines.extend([f"- {project.name}: {project.description or 'No description'}"])
    path = _artifact_path("workspaces", workspace_id, suffix=".md")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return str(path)
