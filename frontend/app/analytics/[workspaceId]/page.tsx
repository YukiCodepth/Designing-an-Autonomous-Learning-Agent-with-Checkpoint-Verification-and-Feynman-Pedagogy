import { apiFetch, demoToken } from "../../../lib/api";

type Analytics = {
  workspace_id: string;
  total_projects: number;
  total_runs: number;
  total_reports: number;
  total_learning_sessions: number;
  total_comments: number;
  total_knowledge_documents: number;
  total_jobs: number;
  checkpoint_pass_rate: number;
  mastery_by_topic: { topic: string; confidence: number; mastered: boolean }[];
  run_volume_by_project: { project_name: string; run_count: number }[];
  report_status_breakdown: { status: string; count: number }[];
  source_quality: { title: string; confidence: number; url: string }[];
  activity_counts: Record<string, number>;
};

async function getAnalytics(workspaceId: string): Promise<Analytics | null> {
  if (!demoToken) {
    return null;
  }
  try {
    return await apiFetch<Analytics>(`/analytics/workspaces/${workspaceId}`, {
      token: demoToken,
    });
  } catch {
    return null;
  }
}

export default async function AnalyticsPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  const analytics = await getAnalytics(workspaceId);

  if (!analytics) {
    return (
      <div className="panel empty">
        Analytics data is unavailable. Set `NEXT_PUBLIC_DEMO_TOKEN` after auth to
        view workspace metrics here.
      </div>
    );
  }

  return (
    <div className="grid cols-2">
      <section className="panel stack">
        <div className="eyebrow">Analytics</div>
        <h2>Workspace overview</h2>
        <div className="grid cols-3">
          <div className="card"><strong>{analytics.total_projects}</strong><div className="muted">Projects</div></div>
          <div className="card"><strong>{analytics.total_runs}</strong><div className="muted">Runs</div></div>
          <div className="card"><strong>{analytics.total_reports}</strong><div className="muted">Reports</div></div>
          <div className="card"><strong>{analytics.total_learning_sessions}</strong><div className="muted">Learning sessions</div></div>
          <div className="card"><strong>{analytics.total_knowledge_documents}</strong><div className="muted">Knowledge docs</div></div>
          <div className="card"><strong>{Math.round(analytics.checkpoint_pass_rate * 100)}%</strong><div className="muted">Checkpoint pass rate</div></div>
        </div>
        <div className="card">
          <h3>Activity counts</h3>
          <div className="meta">
            {Object.entries(analytics.activity_counts).map(([key, value]) => (
              <span key={key}>{key}: {value}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="panel stack">
        <div className="eyebrow">Project load</div>
        <div className="card-list">
          {analytics.run_volume_by_project.map((item) => (
            <div className="card" key={item.project_name}>
              <h3>{item.project_name}</h3>
              <p className="muted">{item.run_count} runs</p>
            </div>
          ))}
        </div>
      </section>

      <section className="panel stack">
        <div className="eyebrow">Mastery</div>
        <div className="card-list">
          {analytics.mastery_by_topic.map((topic) => (
            <div className="card" key={topic.topic}>
              <h3>{topic.topic}</h3>
              <div className="meta">
                <span>Confidence {Math.round(topic.confidence * 100)}%</span>
                <span>{topic.mastered ? "Mastered" : "Needs review"}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel stack">
        <div className="eyebrow">Source quality</div>
        <div className="card-list">
          {analytics.source_quality.map((source) => (
            <a className="card" href={source.url} key={source.url} target="_blank" rel="noreferrer">
              <h3>{source.title}</h3>
              <p className="muted">Confidence {source.confidence}</p>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
