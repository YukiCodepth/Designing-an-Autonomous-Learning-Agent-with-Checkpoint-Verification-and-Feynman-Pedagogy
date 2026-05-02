"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../components/auth-provider";
import { ProtectedRoute } from "../../../components/protected-route";
import {
  apiFetch,
  downloadJobArtifact,
  formatApiError,
  pollJobUntilSettled,
} from "../../../lib/api";
import type { BackgroundJob, Comment, LearningSession, Report, Source, SourceReview } from "../../../lib/types";

type SourceReviewDraft = {
  decision: "pending" | "approved" | "rejected";
  note: string;
};

function ReportPageContent() {
  const { token } = useAuth();
  const params = useParams<{ reportId: string }>();
  const router = useRouter();
  const reportId = params.reportId;

  const [report, setReport] = useState<Report | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusState, setStatusState] = useState<string | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [commentAnchor, setCommentAnchor] = useState("");
  const [commentState, setCommentState] = useState<string | null>(null);
  const [launchState, setLaunchState] = useState<string | null>(null);
  const [learningStyle, setLearningStyle] = useState("");
  const [learningDifficulty, setLearningDifficulty] = useState("");
  const [learningTopics, setLearningTopics] = useState("");
  const [exportState, setExportState] = useState<string | null>(null);
  const [reviewDrafts, setReviewDrafts] = useState<Record<string, SourceReviewDraft>>({});

  async function loadReport() {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [reportResponse, commentResponse] = await Promise.all([
        apiFetch<Report>(`/reports/${reportId}`, { token }),
        apiFetch<Comment[]>(`/reports/${reportId}/comments`, { token }),
      ]);
      setReport(reportResponse);
      setComments(commentResponse);
      setReviewDrafts((current) => {
        const next = { ...current };
        reportResponse.sources.forEach((source) => {
          if (!next[source.id]) {
            next[source.id] = { decision: "approved", note: "" };
          }
        });
        return next;
      });
    } catch (loadError) {
      setError(formatApiError(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
  }, [reportId, token]);

  const sourceReviewMap = useMemo(() => {
    const grouped = new Map<string, SourceReview[]>();
    (report?.source_reviews ?? []).forEach((review) => {
      const current = grouped.get(review.source_id) ?? [];
      grouped.set(review.source_id, [...current, review]);
    });
    return grouped;
  }, [report?.source_reviews]);

  function updateSourceReviewDraft(
    sourceId: string,
    patch: Partial<SourceReviewDraft>,
  ) {
    setReviewDrafts((current) => ({
      ...current,
      [sourceId]: {
        decision: current[sourceId]?.decision ?? "approved",
        note: current[sourceId]?.note ?? "",
        ...patch,
      },
    }));
  }

  function parseTopics(value: string) {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  async function handleStatusUpdate(status: "draft" | "reviewed" | "final") {
    if (!token) {
      return;
    }

    setStatusState("Updating report status...");

    try {
      const updated = await apiFetch<Report>(`/reports/${reportId}/status`, {
        method: "POST",
        token,
        body: { status },
      });
      setReport(updated);
      setStatusState(`Report marked as ${status}.`);
    } catch (statusError) {
      setStatusState(formatApiError(statusError));
    }
  }

  async function handleCommentSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !report) {
      return;
    }

    setCommentState("Saving comment...");

    try {
      const comment = await apiFetch<Comment>(`/reports/${reportId}/comments`, {
        method: "POST",
        token,
        body: {
          body: commentBody,
          anchor: commentAnchor || null,
        },
      });
      setComments((current) => [comment, ...current]);
      setCommentBody("");
      setCommentAnchor("");
      setCommentState("Comment added.");
    } catch (saveError) {
      setCommentState(formatApiError(saveError));
    }
  }

  async function handleSourceReview(source: Source) {
    if (!token) {
      return;
    }

    const draft = reviewDrafts[source.id];
    if (!draft) {
      return;
    }

    try {
      await apiFetch<SourceReview>(`/sources/${source.id}/reviews`, {
        method: "POST",
        token,
        body: draft,
      });
      await loadReport();
    } catch (reviewError) {
      setError(formatApiError(reviewError));
    }
  }

  async function handleLaunchLearning(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setLaunchState("Launching learning session...");

    try {
      const learningSession = await apiFetch<LearningSession>(`/reports/${reportId}/learn`, {
        method: "POST",
        token,
        body: {
          learning_preferences: {
            explanation_style: learningStyle || null,
            difficulty: learningDifficulty || null,
            focus_topics: parseTopics(learningTopics),
          },
        },
      });
      setLaunchState("Learning session created. Redirecting...");
      router.push(`/learning-sessions/${learningSession.id}`);
    } catch (launchError) {
      setLaunchState(formatApiError(launchError));
    }
  }

  async function handleExport(type: "markdown" | "pdf") {
    if (!token) {
      return;
    }

    setExportState(`Queueing ${type.toUpperCase()} export...`);

    try {
      const job = await apiFetch<BackgroundJob>(`/reports/${reportId}/exports/${type}`, {
        method: "POST",
        token,
      });
      const settled = await pollJobUntilSettled<BackgroundJob>(`/jobs/${job.id}`, token);
      if (settled.status === "completed") {
        await downloadJobArtifact(
          settled.id,
          token,
          type === "pdf" ? "report-export.pdf" : "report-export.md",
        );
        setExportState(`${type.toUpperCase()} export downloaded.`);
      } else {
        setExportState(settled.error_message || `${type.toUpperCase()} export failed.`);
      }
    } catch (exportError) {
      setExportState(formatApiError(exportError));
    }
  }

  if (loading) {
    return <div className="panel empty">Loading report...</div>;
  }

  if (error || !report) {
    return <div className="notice error">{error || "Report data is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Cited report</div>
            <h2>{report.title}</h2>
            <p className="muted">{report.executive_summary}</p>
          </div>
          <div className="chip-row">
            <span className="chip">Status: {report.status}</span>
            <span className="chip">{report.sources.length} sources</span>
            <span className="chip">{comments.length} comments</span>
          </div>
        </div>
        <div className="cta-row">
          <Link className="button secondary" href={`/workspaces/${report.workspace_id}/projects/${report.project_id}`}>
            Back to project
          </Link>
          <button className="button secondary" onClick={() => void loadReport()} type="button">
            Refresh
          </button>
          <button className="button secondary" onClick={() => void handleExport("markdown")} type="button">
            Export Markdown
          </button>
          <button className="button secondary" onClick={() => void handleExport("pdf")} type="button">
            Export PDF
          </button>
        </div>
        {statusState ? <div className="notice info">{statusState}</div> : null}
        {exportState ? <div className="notice success">{exportState}</div> : null}
      </section>

      <div className="layout-2">
        <section className="stack">
          <section className="panel stack">
            <div className="eyebrow">Sections</div>
            <div className="card-list">
              {report.sections.map((section) => (
                <article className="card" key={section.id}>
                  <h3>{section.heading}</h3>
                  <p className="muted">{section.body}</p>
                  <div className="chip-row">
                    {section.citation_source_ids.map((sourceId) => (
                      <span className="chip" key={sourceId}>
                        {sourceId}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Comments</div>
            <form className="form-stack" onSubmit={handleCommentSubmit}>
              <label className="field">
                <span>Anchor</span>
                <input
                  onChange={(event) => setCommentAnchor(event.target.value)}
                  placeholder="Optional section or citation id"
                  value={commentAnchor}
                />
              </label>
              <label className="field">
                <span>Comment</span>
                <textarea
                  onChange={(event) => setCommentBody(event.target.value)}
                  placeholder="Add report feedback or collaboration notes"
                  required
                  rows={4}
                  value={commentBody}
                />
              </label>
              {commentState ? <div className="notice info">{commentState}</div> : null}
              <button className="button primary" type="submit">
                Add comment
              </button>
            </form>
            <div className="card-list">
              {comments.map((comment) => (
                <div className="card" key={comment.id}>
                  <p>{comment.body}</p>
                  <div className="meta">
                    <span>{comment.anchor || "general"}</span>
                    <span>{new Date(comment.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>

        <aside className="stack">
          <section className="panel stack">
            <div className="eyebrow">Report controls</div>
            <div className="cta-row">
              <button className="button secondary" onClick={() => void handleStatusUpdate("draft")} type="button">
                Mark draft
              </button>
              <button className="button secondary" onClick={() => void handleStatusUpdate("reviewed")} type="button">
                Mark reviewed
              </button>
              <button className="button secondary" onClick={() => void handleStatusUpdate("final")} type="button">
                Mark final
              </button>
            </div>
            <form className="form-stack" onSubmit={handleLaunchLearning}>
              <h3>Launch learning session</h3>
              <label className="field">
                <span>Explanation style</span>
                <input
                  onChange={(event) => setLearningStyle(event.target.value)}
                  placeholder="clear and practical"
                  value={learningStyle}
                />
              </label>
              <label className="field">
                <span>Difficulty</span>
                <input
                  onChange={(event) => setLearningDifficulty(event.target.value)}
                  placeholder="beginner"
                  value={learningDifficulty}
                />
              </label>
              <label className="field">
                <span>Focus topics</span>
                <input
                  onChange={(event) => setLearningTopics(event.target.value)}
                  placeholder="topic one, topic two"
                  value={learningTopics}
                />
              </label>
              {launchState ? <div className="notice info">{launchState}</div> : null}
              <button className="button primary" type="submit">
                Start learning
              </button>
            </form>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Sources</div>
            <div className="card-list">
              {report.sources.map((source) => (
                <div className="card" key={source.id}>
                  <a href={source.url} rel="noreferrer" target="_blank">
                    <strong>{source.title}</strong>
                  </a>
                  <p className="muted">{source.excerpt || source.summary}</p>
                  <div className="meta">
                    <span>Confidence {source.confidence}</span>
                    <span>{source.published_at || "No publish date"}</span>
                  </div>

                  <div className="card inset-card">
                    <label className="field">
                      <span>Decision</span>
                      <select
                        onChange={(event) =>
                          updateSourceReviewDraft(source.id, {
                            decision: event.target.value as SourceReviewDraft["decision"],
                          })
                        }
                        value={reviewDrafts[source.id]?.decision ?? "approved"}
                      >
                        <option value="pending">Pending</option>
                        <option value="approved">Approve</option>
                        <option value="rejected">Reject</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Review note</span>
                      <textarea
                        onChange={(event) =>
                          updateSourceReviewDraft(source.id, {
                            note: event.target.value,
                          })
                        }
                        placeholder="Why this source is strong or weak"
                        rows={3}
                        value={reviewDrafts[source.id]?.note ?? ""}
                      />
                    </label>
                    <button
                      className="button secondary inline-button"
                      onClick={() => void handleSourceReview(source)}
                      type="button"
                    >
                      Save source review
                    </button>
                  </div>

                  <div className="card-list compact-list">
                    {(sourceReviewMap.get(source.id) ?? []).map((review) => (
                      <div className="card inset-card" key={review.id}>
                        <strong>{review.decision}</strong>
                        <p className="muted">{review.note || "No note provided."}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <ProtectedRoute>
      <ReportPageContent />
    </ProtectedRoute>
  );
}
