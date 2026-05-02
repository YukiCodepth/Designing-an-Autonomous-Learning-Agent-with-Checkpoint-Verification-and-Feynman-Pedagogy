"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../../components/auth-provider";
import { ProtectedRoute } from "../../../components/protected-route";
import {
  apiFetch,
  downloadJobArtifact,
  formatApiError,
  pollJobUntilSettled,
} from "../../../lib/api";
import type {
  BackgroundJob,
  Checkpoint,
  CheckpointSubmissionResponse,
  Comment,
  LearningSession,
} from "../../../lib/types";

type SubmissionState = Record<
  string,
  {
    status: string;
    nextAction?: string;
  }
>;

function LearningSessionPageContent() {
  const { token } = useAuth();
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const [session, setSession] = useState<LearningSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [submissionState, setSubmissionState] = useState<SubmissionState>({});
  const [commentBody, setCommentBody] = useState("");
  const [commentAnchor, setCommentAnchor] = useState("");
  const [commentState, setCommentState] = useState<string | null>(null);
  const [exportState, setExportState] = useState<string | null>(null);

  async function loadSession() {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await apiFetch<LearningSession>(`/learning-sessions/${sessionId}`, { token });
      setSession(response);
      setAnswers((current) => {
        const next = { ...current };
        response.checkpoints.forEach((checkpoint) => {
          next[checkpoint.id] =
            current[checkpoint.id] ??
            checkpoint.quiz_questions.map((_, index) => checkpoint.last_answers?.[index] ?? "");
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
    void loadSession();
  }, [sessionId, token]);

  function updateCheckpoint(checkpointId: string, questionIndex: number, value: string) {
    setAnswers((current) => ({
      ...current,
      [checkpointId]: current[checkpointId].map((answer, index) =>
        index === questionIndex ? value : answer,
      ),
    }));
  }

  async function submitCheckpoint(checkpoint: Checkpoint) {
    if (!token) {
      return;
    }

    setSubmissionState((current) => ({
      ...current,
      [checkpoint.id]: { status: "Submitting answers..." },
    }));

    try {
      const response = await apiFetch<CheckpointSubmissionResponse>(`/checkpoints/${checkpoint.id}/submit`, {
        method: "POST",
        token,
        body: {
          answers: answers[checkpoint.id].filter((answer) => answer.trim().length > 0),
          preferred_explanation_style: session?.preferred_explanation_style || null,
        },
      });

      setSession((current) =>
        current
          ? {
              ...current,
              checkpoints: current.checkpoints.map((item) =>
                item.id === checkpoint.id ? response.checkpoint : item,
              ),
            }
          : current,
      );
      setSubmissionState((current) => ({
        ...current,
        [checkpoint.id]: {
          status: `Saved. Confidence ${Math.round(response.mastery_record.confidence * 100)}%.`,
          nextAction: response.next_recommended_action,
        },
      }));
    } catch (submitError) {
      setSubmissionState((current) => ({
        ...current,
        [checkpoint.id]: { status: formatApiError(submitError) },
      }));
    }
  }

  async function handleCommentSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !session) {
      return;
    }

    setCommentState("Saving session comment...");

    try {
      const comment = await apiFetch<Comment>(`/learning-sessions/${sessionId}/comments`, {
        method: "POST",
        token,
        body: {
          body: commentBody,
          anchor: commentAnchor || null,
        },
      });
      setSession((current) =>
        current
          ? {
              ...current,
              comments: [comment, ...current.comments],
            }
          : current,
      );
      setCommentBody("");
      setCommentAnchor("");
      setCommentState("Comment added.");
    } catch (commentError) {
      setCommentState(formatApiError(commentError));
    }
  }

  async function handleExportSummary() {
    if (!token) {
      return;
    }

    setExportState("Queueing summary export...");

    try {
      const job = await apiFetch<BackgroundJob>(`/learning-sessions/${sessionId}/exports/summary`, {
        method: "POST",
        token,
      });
      const settled = await pollJobUntilSettled<BackgroundJob>(`/jobs/${job.id}`, token);
      if (settled.status === "completed") {
        await downloadJobArtifact(settled.id, token, "learning-session-summary.md");
        setExportState("Learning session summary downloaded.");
      } else {
        setExportState(settled.error_message || "Learning session export failed.");
      }
    } catch (exportError) {
      setExportState(formatApiError(exportError));
    }
  }

  if (loading) {
    return <div className="panel empty">Loading learning session...</div>;
  }

  if (error || !session) {
    return <div className="notice error">{error || "Learning session data is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Learning session</div>
            <h2>Checkpoint progression</h2>
            <p className="muted">
              Work through the checkpoints, submit answers, and use the feedback
              loop to strengthen mastery.
            </p>
          </div>
          <div className="chip-row">
            <span className="chip">Status: {session.status}</span>
            <span className="chip">Current checkpoint: {session.current_checkpoint_index + 1}</span>
            {session.preferred_explanation_style ? (
              <span className="chip">Style: {session.preferred_explanation_style}</span>
            ) : null}
          </div>
        </div>
        <div className="cta-row">
          <Link className="button secondary" href={`/reports/${session.report_id}`}>
            Back to report
          </Link>
          <button className="button secondary" onClick={() => void loadSession()} type="button">
            Refresh
          </button>
          <button className="button primary" onClick={() => void handleExportSummary()} type="button">
            Export summary
          </button>
        </div>
        {exportState ? <div className="notice success">{exportState}</div> : null}
      </section>

      <div className="layout-2">
        <section className="stack">
          {session.checkpoints.map((checkpoint) => (
            <section className="panel stack" key={checkpoint.id}>
              <div className="eyebrow">Checkpoint {checkpoint.order_index + 1}</div>
              <h3>{checkpoint.title}</h3>
              <p className="muted">{checkpoint.objective}</p>
              <div className="study-copy">{checkpoint.study_material}</div>

              <div className="form-stack">
                {checkpoint.quiz_questions.map((question, index) => (
                  <label className="field" key={`${checkpoint.id}-${index}`}>
                    <span>{question}</span>
                    <textarea
                      onChange={(event) =>
                        updateCheckpoint(checkpoint.id, index, event.target.value)
                      }
                      rows={3}
                      value={answers[checkpoint.id]?.[index] ?? ""}
                    />
                  </label>
                ))}
                <button
                  className="button primary"
                  onClick={() => void submitCheckpoint(checkpoint)}
                  type="button"
                >
                  Submit answers
                </button>
              </div>

              <div className="meta">
                <span>Score: {checkpoint.score ?? "Not graded yet"}</span>
                <span>Passed: {checkpoint.passed === null ? "Pending" : String(checkpoint.passed)}</span>
              </div>

              {checkpoint.feedback ? (
                <div className="card inset-card">
                  <strong>Feedback</strong>
                  <p className="muted">{checkpoint.feedback}</p>
                  {checkpoint.simplified_material ? (
                    <>
                      <strong>Simplified explanation</strong>
                      <p className="muted">{checkpoint.simplified_material}</p>
                    </>
                  ) : null}
                </div>
              ) : null}

              {submissionState[checkpoint.id] ? (
                <div className="notice info">
                  <div>{submissionState[checkpoint.id].status}</div>
                  {submissionState[checkpoint.id].nextAction ? (
                    <div className="muted">{submissionState[checkpoint.id].nextAction}</div>
                  ) : null}
                </div>
              ) : null}
            </section>
          ))}
        </section>

        <aside className="stack">
          <section className="panel stack">
            <div className="eyebrow">Session comments</div>
            <form className="form-stack" onSubmit={handleCommentSubmit}>
              <label className="field">
                <span>Anchor</span>
                <input
                  onChange={(event) => setCommentAnchor(event.target.value)}
                  placeholder="Optional checkpoint id or topic"
                  value={commentAnchor}
                />
              </label>
              <label className="field">
                <span>Comment</span>
                <textarea
                  onChange={(event) => setCommentBody(event.target.value)}
                  placeholder="Mentor note or peer feedback"
                  required
                  rows={4}
                  value={commentBody}
                />
              </label>
              {commentState ? <div className="notice info">{commentState}</div> : null}
              <button className="button secondary" type="submit">
                Add session comment
              </button>
            </form>
            <div className="card-list">
              {session.comments.map((comment) => (
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
        </aside>
      </div>
    </div>
  );
}

export default function LearningSessionPage() {
  return (
    <ProtectedRoute>
      <LearningSessionPageContent />
    </ProtectedRoute>
  );
}
