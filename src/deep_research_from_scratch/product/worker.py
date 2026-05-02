"""Background worker for ingestion and export jobs."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select

from deep_research_from_scratch.product.config import settings
from deep_research_from_scratch.product.db import SessionLocal
from deep_research_from_scratch.product.exporters import (
    export_learning_session_summary,
    export_report_markdown,
    export_report_pdf,
    export_workspace_summary,
)
from deep_research_from_scratch.product.knowledge import (
    ensure_product_dirs,
    extract_text_from_file,
    fetch_url_text,
    upsert_document_chunks,
)
from deep_research_from_scratch.product.models import (
    BackgroundJob,
    BackgroundJobStatus,
    BackgroundJobType,
    KnowledgeDocument,
    KnowledgeDocumentKind,
    KnowledgeDocumentStatus,
)


def _claim_next_job():
    with SessionLocal() as db:
        job = db.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.status == BackgroundJobStatus.pending,
                BackgroundJob.run_after <= datetime.now(timezone.utc),
            )
            .order_by(BackgroundJob.created_at.asc())
        )
        if not job:
            return None
        job.status = BackgroundJobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job


def _complete_job(job_id: str, *, artifact_path: str | None = None, result_payload: dict | None = None) -> None:
    with SessionLocal() as db:
        job = db.get(BackgroundJob, job_id)
        if not job:
            return
        job.status = BackgroundJobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        job.artifact_path = artifact_path
        job.result_payload = result_payload or {}
        db.commit()


def _fail_job(job_id: str, error_message: str) -> None:
    with SessionLocal() as db:
        job = db.get(BackgroundJob, job_id)
        if not job:
            return
        job.status = BackgroundJobStatus.failed
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


def _process_document_job(job_id: str, document_id: str, *, from_url: bool) -> dict:
    with SessionLocal() as db:
        document = db.get(KnowledgeDocument, document_id)
        if not document:
            raise ValueError("Knowledge document not found.")

        if from_url:
            content = fetch_url_text(document.source_uri or "")
        else:
            inferred_kind = document.kind
            if inferred_kind == KnowledgeDocumentKind.url:
                inferred_kind = KnowledgeDocumentKind.text
            content = extract_text_from_file(document.source_uri or "", inferred_kind)

        chunk_count = upsert_document_chunks(
            db,
            document,
            content_text=content,
            metadata_json=document.metadata_json,
        )
        document.status = KnowledgeDocumentStatus.ready
        db.commit()
        return {"document_id": document.id, "chunk_count": chunk_count}


def process_job(job_id: str) -> None:
    """Run a single job by id."""
    with SessionLocal() as db:
        job = db.get(BackgroundJob, job_id)
        if not job:
            raise ValueError("Job not found.")
        payload = job.payload or {}
        job_type = job.job_type

    try:
        if job_type == BackgroundJobType.ingest_document:
            result = _process_document_job(job_id, payload["document_id"], from_url=False)
            _complete_job(job_id, result_payload=result)
            return
        if job_type == BackgroundJobType.ingest_url:
            result = _process_document_job(job_id, payload["document_id"], from_url=True)
            _complete_job(job_id, result_payload=result)
            return
        if job_type == BackgroundJobType.export_report_markdown:
            with SessionLocal() as db:
                artifact_path = export_report_markdown(db, payload["report_id"])
            _complete_job(job_id, artifact_path=artifact_path)
            return
        if job_type == BackgroundJobType.export_report_pdf:
            with SessionLocal() as db:
                artifact_path = export_report_pdf(db, payload["report_id"])
            _complete_job(job_id, artifact_path=artifact_path)
            return
        if job_type == BackgroundJobType.export_learning_session_summary:
            with SessionLocal() as db:
                artifact_path = export_learning_session_summary(db, payload["learning_session_id"])
            _complete_job(job_id, artifact_path=artifact_path)
            return
        if job_type == BackgroundJobType.export_workspace_summary:
            with SessionLocal() as db:
                artifact_path = export_workspace_summary(db, payload["workspace_id"])
            _complete_job(job_id, artifact_path=artifact_path)
            return
        raise ValueError(f"Unsupported job type: {job_type}")
    except Exception as exc:  # pragma: no cover - runtime safeguard
        _fail_job(job_id, str(exc))


def run_worker_forever() -> None:
    """Continuously poll and process pending jobs."""
    ensure_product_dirs()
    while True:
        job = _claim_next_job()
        if not job:
            time.sleep(settings.worker_poll_seconds)
            continue
        process_job(job.id)


if __name__ == "__main__":  # pragma: no cover
    run_worker_forever()
