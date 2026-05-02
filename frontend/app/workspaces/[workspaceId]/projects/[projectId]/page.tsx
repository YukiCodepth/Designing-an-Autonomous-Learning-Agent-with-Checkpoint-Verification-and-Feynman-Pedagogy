import Link from "next/link";

import { apiFetch, demoToken } from "../../../../../lib/api";

type ProjectDetail = {
  project: {
    id: string;
    name: string;
    description: string | null;
    assigned_user_id: string | null;
  };
  reports: {
    id: string;
    title: string;
    executive_summary: string;
    created_at: string;
    status: string;
    sources: { id: string }[];
  }[];
  runs: {
    id: string;
    mode: string;
    status: string;
    created_at: string;
  }[];
  knowledge_documents: {
    id: string;
    title: string;
    kind: string;
    status: string;
    chunk_count: number;
  }[];
  review_flags: {
    id: string;
    severity: string;
    note: string;
    created_at: string;
  }[];
};

async function getProject(projectId: string): Promise<ProjectDetail | null> {
  if (!demoToken) {
    return null;
  }
  try {
    return await apiFetch<ProjectDetail>(`/projects/${projectId}/detail`, { token: demoToken });
  } catch {
    return null;
  }
}

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ workspaceId: string; projectId: string }>;
}) {
  const { workspaceId, projectId } = await params;
  const detail = await getProject(projectId);

  if (!detail) {
    return (
      <div className="panel empty">
        Project data is unavailable. Use a live backend token to populate the dashboard.
      </div>
    );
  }

  const { project, reports, runs, knowledge_documents, review_flags } = detail;

  return (
    <div className="layout-2">
      <section className="panel stack">
        <div className="eyebrow">Project</div>
        <h2>{project.name}</h2>
        <p className="muted">{project.description || "No description yet."}</p>
        <div className="chip-row">
          <span className="chip">{runs.length} runs</span>
          <span className="chip">{reports.length} reports</span>
          <span className="chip">{knowledge_documents.length} knowledge documents</span>
          <span className="chip">{review_flags.length} review flags</span>
        </div>
        {project.assigned_user_id ? <p className="muted">Assigned to: {project.assigned_user_id}</p> : null}

        <div className="card-list">
          {reports.map((report) => (
            <Link
              href={`/reports/${report.id}`}
              className="card"
              key={report.id}
            >
              <h3>{report.title}</h3>
              <p className="muted">{report.executive_summary}</p>
              <div className="meta">
                <span>{report.status}</span>
                <span>{report.sources.length} sources</span>
                <span>{new Date(report.created_at).toLocaleString()}</span>
              </div>
            </Link>
          ))}
          {reports.length === 0 ? (
            <div className="empty">Run the copilot through the backend API to create your first cited report.</div>
          ) : null}
        </div>
      </section>

      <aside className="panel">
        <div className="eyebrow">Run history</div>
        <div className="card-list">
          {runs.map((run) => (
            <div className="card" key={run.id}>
              <h3 style={{ marginBottom: 6 }}>{run.mode}</h3>
              <div className="meta">
                <span>{run.status}</span>
                <span>{new Date(run.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))}
          {runs.length === 0 ? (
            <div className="empty">
              Use `POST /projects/:projectId/runs` with mode `research`,
              `learn`, or `research_then_learn` to populate this history.
            </div>
          ) : null}
        </div>
        <div className="eyebrow" style={{ marginTop: 24 }}>Knowledge Base</div>
        <div className="card-list">
          {knowledge_documents.length === 0 ? (
            <div className="empty">
              Add notes, URLs, PDFs, or markdown files through the knowledge endpoints
              to make private retrieval available to the copilot.
            </div>
          ) : (
            knowledge_documents.map((document) => (
              <div className="card" key={document.id}>
                <h3 style={{ marginBottom: 6 }}>{document.title}</h3>
                <div className="meta">
                  <span>{document.kind}</span>
                  <span>{document.status}</span>
                  <span>{document.chunk_count} chunks</span>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="eyebrow" style={{ marginTop: 24 }}>Human Review</div>
        <div className="card-list">
          {review_flags.length === 0 ? (
            <div className="empty">
              No review flags yet. Use the review endpoints when you want a human
              to track hallucination risk, weak evidence, or quality concerns.
            </div>
          ) : (
            review_flags.map((flag) => (
              <div className="card" key={flag.id}>
                <h3 style={{ marginBottom: 6 }}>{flag.severity}</h3>
                <p className="muted">{flag.note}</p>
                <div className="meta">
                  <span>{new Date(flag.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="cta-row">
          <Link
            className="button secondary"
            href={`/workspaces/${workspaceId}`}
          >
            Back to workspace
          </Link>
          <Link className="button secondary" href={`/analytics/${workspaceId}`}>
            Workspace analytics
          </Link>
        </div>
      </aside>
    </div>
  );
}
