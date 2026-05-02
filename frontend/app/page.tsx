import Link from "next/link";

export default function HomePage() {
  return (
    <div className="grid cols-2">
      <section className="panel stack">
        <div className="eyebrow">Research + Learning</div>
        <h2 style={{ marginBottom: 0 }}>One workflow from question to mastery</h2>
        <p className="muted">
          This product layer turns the existing LangGraph demo into a collaborative
          workspace where teams can run cited research, save reports, launch
          learning sessions, track checkpoint performance, and build topic mastery.
        </p>
        <div className="chip-row">
          <span className="chip">Shared workspaces</span>
          <span className="chip">Cited report viewer</span>
          <span className="chip">Adaptive checkpoint sessions</span>
          <span className="chip">Project runs + history</span>
        </div>
        <div className="cta-row">
          <Link className="button primary" href="/workspaces">
            Open dashboard
          </Link>
          <Link className="button secondary" href="/login">
            Try auth flow
          </Link>
        </div>
      </section>

      <section className="panel stack">
        <div className="eyebrow">API Surface</div>
        <h2 style={{ marginBottom: 0 }}>Built around the new product backend</h2>
        <ul className="list muted">
          <li>`/auth/*` for registration, login, and current-user identity</li>
          <li>`/workspaces` and `/projects` for collaboration structure</li>
          <li>`/projects/:projectId/runs` for the unified `copilot_v2` graph</li>
          <li>`/reports/:reportId` for cited reports and source viewers</li>
          <li>`/learning-sessions/:sessionId` and `/checkpoints/:id/submit` for learning continuity</li>
        </ul>
      </section>

      <section className="panel">
        <div className="eyebrow">Experience Map</div>
        <div className="grid cols-3">
          <div className="card">
            <h3>1. Create or join a workspace</h3>
            <p className="muted">
              Organize research by team, project, and shared run history instead of
              isolated notebook sessions.
            </p>
          </div>
          <div className="card">
            <h3>2. Run the copilot</h3>
            <p className="muted">
              Choose `research`, `learn`, or `research_then_learn` and persist the
              output as product objects, not loose markdown files.
            </p>
          </div>
          <div className="card">
            <h3>3. Grow mastery over time</h3>
            <p className="muted">
              Track checkpoints, scores, remediation loops, and topic-level
              confidence across sessions.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
