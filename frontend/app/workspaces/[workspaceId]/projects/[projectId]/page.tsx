"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../../../../../components/auth-provider";
import { ProtectedRoute } from "../../../../../components/protected-route";
import {
  apiFetch,
  downloadJobArtifact,
  formatApiError,
  pollJobUntilSettled,
} from "../../../../../lib/api";
import type {
  BackgroundJob,
  KnowledgeDocument,
  KnowledgeSearchHit,
  KnowledgeSearchResponse,
  ProjectDetail,
  ProjectRun,
  RunReviewFlag,
} from "../../../../../lib/types";

function parseTopics(value: string): string[] {
  return value
    .split(",")
    .map((topic) => topic.trim())
    .filter(Boolean);
}

function ProjectPageContent() {
  const { token } = useAuth();
  const params = useParams<{ workspaceId: string; projectId: string }>();
  const router = useRouter();
  const workspaceId = params.workspaceId;
  const projectId = params.projectId;

  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<"research" | "learn" | "research_then_learn">("research_then_learn");
  const [message, setMessage] = useState("");
  const [explanationStyle, setExplanationStyle] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [focusTopics, setFocusTopics] = useState("");
  const [runState, setRunState] = useState<string | null>(null);

  const [noteTitle, setNoteTitle] = useState("");
  const [noteContent, setNoteContent] = useState("");
  const [noteState, setNoteState] = useState<string | null>(null);

  const [urlTitle, setUrlTitle] = useState("");
  const [urlValue, setUrlValue] = useState("");
  const [urlState, setUrlState] = useState<string | null>(null);

  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentState, setDocumentState] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<KnowledgeSearchHit[]>([]);
  const [searchState, setSearchState] = useState<string | null>(null);

  const [reviewSeverity, setReviewSeverity] = useState("medium");
  const [reviewNote, setReviewNote] = useState("");
  const [reviewRunId, setReviewRunId] = useState("");
  const [reviewState, setReviewState] = useState<string | null>(null);

  async function loadProject() {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [projectDetail, workspaceJobs] = await Promise.all([
        apiFetch<ProjectDetail>(`/projects/${projectId}/detail`, { token }),
        apiFetch<BackgroundJob[]>(`/workspaces/${workspaceId}/jobs`, { token }),
      ]);
      setDetail(projectDetail);
      setJobs(workspaceJobs.filter((job) => job.project_id === projectId));
    } catch (loadError) {
      setError(formatApiError(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadProject();
  }, [token, projectId, workspaceId]);

  const recentRuns = useMemo(() => detail?.runs ?? [], [detail]);

  async function handleRunCopilot(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setRunState("Launching copilot...");

    try {
      const run = await apiFetch<ProjectRun>(`/projects/${projectId}/runs`, {
        method: "POST",
        token,
        body: {
          mode,
          messages: [{ role: "user", content: message }],
          learning_preferences: {
            explanation_style: explanationStyle || null,
            difficulty: difficulty || null,
            focus_topics: parseTopics(focusTopics),
          },
        },
      });

      setRunState("Run completed. Redirecting into the result...");
      await loadProject();

      if (run.learning_session?.id) {
        router.push(`/learning-sessions/${run.learning_session.id}`);
        return;
      }

      if (run.report?.id) {
        router.push(`/reports/${run.report.id}`);
        return;
      }

      setRunState("Run finished, but no report or learning session was returned.");
    } catch (runError) {
      setRunState(formatApiError(runError));
    }
  }

  async function handleCreateNote(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setNoteState("Creating knowledge note...");

    try {
      const document = await apiFetch<KnowledgeDocument>(`/projects/${projectId}/knowledge/notes`, {
        method: "POST",
        token,
        body: {
          title: noteTitle,
          content: noteContent,
          kind: "note",
          metadata_json: {},
        },
      });

      setDetail((current) =>
        current
          ? {
              ...current,
              knowledge_documents: [document, ...current.knowledge_documents],
            }
          : current,
      );
      setNoteTitle("");
      setNoteContent("");
      setNoteState("Note added to the project knowledge base.");
    } catch (noteError) {
      setNoteState(formatApiError(noteError));
    }
  }

  async function handleQueueUrl(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setUrlState("Queueing URL ingestion...");

    try {
      const job = await apiFetch<BackgroundJob>(`/projects/${projectId}/knowledge/urls`, {
        method: "POST",
        token,
        body: {
          url: urlValue,
          title: urlTitle || null,
        },
      });
      const settled = await pollJobUntilSettled<BackgroundJob>(`/jobs/${job.id}`, token);
      setJobs((current) => [settled, ...current.filter((item) => item.id !== settled.id)]);
      setUrlTitle("");
      setUrlValue("");
      setUrlState(
        settled.status === "completed"
          ? "URL ingested successfully."
          : settled.error_message || "URL ingestion failed.",
      );
      await loadProject();
    } catch (urlError) {
      setUrlState(formatApiError(urlError));
    }
  }

  async function handleUploadDocument(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !documentFile) {
      return;
    }

    setDocumentState("Uploading and queueing document ingestion...");

    try {
      const formData = new FormData();
      formData.append("file", documentFile);
      const job = await apiFetch<BackgroundJob>(`/projects/${projectId}/knowledge/documents`, {
        method: "POST",
        token,
        body: formData,
      });
      const settled = await pollJobUntilSettled<BackgroundJob>(`/jobs/${job.id}`, token);
      setJobs((current) => [settled, ...current.filter((item) => item.id !== settled.id)]);
      setDocumentFile(null);
      setDocumentState(
        settled.status === "completed"
          ? "Document ingestion completed."
          : settled.error_message || "Document ingestion failed.",
      );
      await loadProject();
    } catch (uploadError) {
      setDocumentState(formatApiError(uploadError));
    }
  }

  async function handleSearchKnowledge(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setSearchState("Searching private knowledge...");

    try {
      const response = await apiFetch<KnowledgeSearchResponse>(`/projects/${projectId}/knowledge/search`, {
        method: "POST",
        token,
        body: {
          query: searchQuery,
          limit: 8,
        },
      });
      setSearchHits(response.hits);
      setSearchState(`${response.hits.length} results found.`);
    } catch (searchError) {
      setSearchState(formatApiError(searchError));
    }
  }

  async function handleCreateReviewFlag(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !reviewRunId) {
      return;
    }

    setReviewState("Saving review flag...");

    try {
      const flag = await apiFetch<RunReviewFlag>(`/runs/${reviewRunId}/review-flags`, {
        method: "POST",
        token,
        body: {
          severity: reviewSeverity,
          note: reviewNote,
          report_id: null,
        },
      });
      setDetail((current) =>
        current
          ? {
              ...current,
              review_flags: [flag, ...current.review_flags],
            }
          : current,
      );
      setReviewNote("");
      setReviewState("Review flag added.");
    } catch (flagError) {
      setReviewState(formatApiError(flagError));
    }
  }

  if (loading) {
    return <div className="panel empty">Loading project hub...</div>;
  }

  if (error || !detail) {
    return <div className="notice error">{error || "Project data is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Project hub</div>
            <h2>{detail.project.name}</h2>
            <p className="muted">{detail.project.description || "No description yet."}</p>
          </div>
          <div className="chip-row">
            <span className="chip">{detail.runs.length} runs</span>
            <span className="chip">{detail.reports.length} reports</span>
            <span className="chip">{detail.knowledge_documents.length} knowledge docs</span>
            <span className="chip">{detail.review_flags.length} review flags</span>
          </div>
        </div>
        <div className="cta-row">
          <Link className="button secondary" href={`/workspaces/${workspaceId}`}>
            Back to workspace
          </Link>
          <button className="button secondary" onClick={() => void loadProject()} type="button">
            Refresh
          </button>
        </div>
      </section>

      <div className="layout-2">
        <section className="stack">
          <section className="panel stack">
            <div className="eyebrow">Run copilot</div>
            <form className="form-stack" onSubmit={handleRunCopilot}>
              <label className="field">
                <span>Mode</span>
                <select onChange={(event) => setMode(event.target.value as typeof mode)} value={mode}>
                  <option value="research">Research</option>
                  <option value="learn">Learn</option>
                  <option value="research_then_learn">Research then learn</option>
                </select>
              </label>
              <label className="field">
                <span>Primary message</span>
                <textarea
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="Describe what you want the copilot to research or teach."
                  required
                  rows={6}
                  value={message}
                />
              </label>
              <div className="grid cols-3">
                <label className="field">
                  <span>Explanation style</span>
                  <input
                    onChange={(event) => setExplanationStyle(event.target.value)}
                    placeholder="clear and practical"
                    value={explanationStyle}
                  />
                </label>
                <label className="field">
                  <span>Difficulty</span>
                  <input
                    onChange={(event) => setDifficulty(event.target.value)}
                    placeholder="beginner"
                    value={difficulty}
                  />
                </label>
                <label className="field">
                  <span>Focus topics</span>
                  <input
                    onChange={(event) => setFocusTopics(event.target.value)}
                    placeholder="checkpoint verification, feynman pedagogy"
                    value={focusTopics}
                  />
                </label>
              </div>
              {runState ? <div className="notice info">{runState}</div> : null}
              <button className="button primary" type="submit">
                Run copilot
              </button>
            </form>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Reports</div>
            <div className="card-list">
              {detail.reports.length === 0 ? (
                <div className="empty">Run the copilot to create the first report.</div>
              ) : (
                detail.reports.map((report) => (
                  <Link className="card interactive-card" href={`/reports/${report.id}`} key={report.id}>
                    <h3>{report.title}</h3>
                    <p className="muted">{report.executive_summary}</p>
                    <div className="meta">
                      <span>{report.status}</span>
                      <span>{report.sources.length} sources</span>
                      <span>{new Date(report.created_at).toLocaleString()}</span>
                    </div>
                  </Link>
                ))
              )}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Knowledge base</div>
            <div className="grid cols-2">
              <form className="form-stack form-card" onSubmit={handleCreateNote}>
                <h3>Add note</h3>
                <label className="field">
                  <span>Title</span>
                  <input
                    onChange={(event) => setNoteTitle(event.target.value)}
                    placeholder="Course concept notes"
                    required
                    value={noteTitle}
                  />
                </label>
                <label className="field">
                  <span>Content</span>
                  <textarea
                    onChange={(event) => setNoteContent(event.target.value)}
                    placeholder="Paste project knowledge here"
                    required
                    rows={5}
                    value={noteContent}
                  />
                </label>
                {noteState ? <div className="notice info">{noteState}</div> : null}
                <button className="button primary" type="submit">
                  Save note
                </button>
              </form>

              <form className="form-stack form-card" onSubmit={handleQueueUrl}>
                <h3>Queue URL ingestion</h3>
                <label className="field">
                  <span>URL</span>
                  <input
                    onChange={(event) => setUrlValue(event.target.value)}
                    placeholder="https://example.com/article"
                    required
                    type="url"
                    value={urlValue}
                  />
                </label>
                <label className="field">
                  <span>Title</span>
                  <input
                    onChange={(event) => setUrlTitle(event.target.value)}
                    placeholder="Optional title override"
                    value={urlTitle}
                  />
                </label>
                {urlState ? <div className="notice info">{urlState}</div> : null}
                <button className="button primary" type="submit">
                  Queue URL
                </button>
              </form>
            </div>

            <form className="form-stack form-card" onSubmit={handleUploadDocument}>
              <h3>Upload document</h3>
              <label className="field">
                <span>File</span>
                <input
                  onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)}
                  required
                  type="file"
                />
              </label>
              {documentState ? <div className="notice info">{documentState}</div> : null}
              <button className="button primary" type="submit">
                Upload document
              </button>
            </form>

            <form className="form-stack" onSubmit={handleSearchKnowledge}>
              <h3>Search project knowledge</h3>
              <label className="field">
                <span>Query</span>
                <input
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search ingested notes, urls, and files"
                  required
                  value={searchQuery}
                />
              </label>
              {searchState ? <div className="notice info">{searchState}</div> : null}
              <button className="button secondary" type="submit">
                Search knowledge
              </button>
            </form>

            <div className="card-list">
              {searchHits.map((hit) => (
                <div className="card" key={hit.chunk_id}>
                  <strong>{hit.document_title}</strong>
                  <p className="muted">{hit.content}</p>
                  <div className="meta">
                    <span>Score {hit.score.toFixed(3)}</span>
                    <span>{hit.document_id}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="card-list">
              {detail.knowledge_documents.map((document) => (
                <div className="card" key={document.id}>
                  <strong>{document.title}</strong>
                  <div className="meta">
                    <span>{document.kind}</span>
                    <span>{document.status}</span>
                    <span>{document.chunk_count} chunks</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>

        <aside className="stack">
          <section className="panel stack">
            <div className="eyebrow">Run history</div>
            <div className="card-list">
              {recentRuns.length === 0 ? (
                <div className="empty">No runs yet.</div>
              ) : (
                recentRuns.map((run) => (
                  <div className="card" key={run.id}>
                    <strong>{run.mode}</strong>
                    <div className="meta">
                      <span>{run.status}</span>
                      <span>{new Date(run.created_at).toLocaleString()}</span>
                    </div>
                    {run.error_message ? <div className="notice error">{run.error_message}</div> : null}
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Review flags</div>
            <form className="form-stack" onSubmit={handleCreateReviewFlag}>
              <label className="field">
                <span>Run</span>
                <select onChange={(event) => setReviewRunId(event.target.value)} required value={reviewRunId}>
                  <option value="">Select a run</option>
                  {recentRuns.map((run) => (
                    <option key={run.id} value={run.id}>
                      {run.mode} · {run.status}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Severity</span>
                <select onChange={(event) => setReviewSeverity(event.target.value)} value={reviewSeverity}>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </label>
              <label className="field">
                <span>Note</span>
                <textarea
                  onChange={(event) => setReviewNote(event.target.value)}
                  placeholder="Call out evidence quality or hallucination risk"
                  required
                  rows={4}
                  value={reviewNote}
                />
              </label>
              {reviewState ? <div className="notice info">{reviewState}</div> : null}
              <button className="button secondary" type="submit">
                Add review flag
              </button>
            </form>
            <div className="card-list">
              {detail.review_flags.map((flag) => (
                <div className="card" key={flag.id}>
                  <strong>{flag.severity}</strong>
                  <p className="muted">{flag.note}</p>
                  <div className="meta">
                    <span>Run {flag.run_id}</span>
                    <span>{new Date(flag.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Background jobs</div>
            <div className="card-list">
              {jobs.length === 0 ? (
                <div className="empty">No jobs for this project yet.</div>
              ) : (
                jobs.map((job) => (
                  <div className="card" key={job.id}>
                    <strong>{job.job_type}</strong>
                    <div className="meta">
                      <span>{job.status}</span>
                      <span>{new Date(job.created_at).toLocaleString()}</span>
                    </div>
                    {job.artifact_path ? (
                      <button
                        className="button secondary inline-button"
                        onClick={() => token && downloadJobArtifact(job.id, token)}
                        type="button"
                      >
                        Download artifact
                      </button>
                    ) : null}
                    {job.error_message ? <div className="notice error">{job.error_message}</div> : null}
                  </div>
                ))
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

export default function ProjectPage() {
  return (
    <ProtectedRoute>
      <ProjectPageContent />
    </ProtectedRoute>
  );
}
