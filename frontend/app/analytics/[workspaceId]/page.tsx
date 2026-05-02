"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../../components/auth-provider";
import { ProtectedRoute } from "../../../components/protected-route";
import { apiFetch, formatApiError } from "../../../lib/api";
import type { Analytics } from "../../../lib/types";

function AnalyticsPageContent() {
  const { token } = useAuth();
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;

  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAnalytics() {
      if (!token) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await apiFetch<Analytics>(`/analytics/workspaces/${workspaceId}`, {
          token,
        });
        setAnalytics(response);
      } catch (loadError) {
        setError(formatApiError(loadError));
      } finally {
        setLoading(false);
      }
    }

    void loadAnalytics();
  }, [token, workspaceId]);

  if (loading) {
    return <div className="panel empty">Loading analytics...</div>;
  }

  if (error || !analytics) {
    return <div className="notice error">{error || "Analytics data is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Analytics</div>
            <h2>Workspace overview</h2>
            <p className="muted">
              Track project activity, run volume, mastery trends, source quality,
              and operational load across the workspace.
            </p>
          </div>
          <Link className="button secondary" href={`/workspaces/${workspaceId}`}>
            Back to workspace
          </Link>
        </div>
      </section>

      <div className="grid cols-3">
        <div className="card metric-card"><strong>{analytics.total_projects}</strong><span>Projects</span></div>
        <div className="card metric-card"><strong>{analytics.total_runs}</strong><span>Runs</span></div>
        <div className="card metric-card"><strong>{analytics.total_reports}</strong><span>Reports</span></div>
        <div className="card metric-card"><strong>{analytics.total_learning_sessions}</strong><span>Learning sessions</span></div>
        <div className="card metric-card"><strong>{analytics.total_jobs}</strong><span>Jobs</span></div>
        <div className="card metric-card"><strong>{Math.round(analytics.checkpoint_pass_rate * 100)}%</strong><span>Checkpoint pass rate</span></div>
      </div>

      <div className="layout-2">
        <section className="panel stack">
          <div className="eyebrow">Run volume by project</div>
          <div className="card-list">
            {analytics.run_volume_by_project.map((item) => (
              <div className="card" key={item.project_name}>
                <strong>{item.project_name}</strong>
                <div className="meta">
                  <span>{item.run_count} runs</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel stack">
          <div className="eyebrow">Mastery by topic</div>
          <div className="card-list">
            {analytics.mastery_by_topic.map((topic) => (
              <div className="card" key={topic.topic}>
                <strong>{topic.topic}</strong>
                <div className="meta">
                  <span>Confidence {Math.round(topic.confidence * 100)}%</span>
                  <span>{topic.mastered ? "Mastered" : "Needs review"}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="layout-2">
        <section className="panel stack">
          <div className="eyebrow">Source quality</div>
          <div className="card-list">
            {analytics.source_quality.map((source) => (
              <a className="card interactive-card" href={source.url} key={source.url} rel="noreferrer" target="_blank">
                <strong>{source.title}</strong>
                <div className="meta">
                  <span>Confidence {source.confidence}</span>
                </div>
              </a>
            ))}
          </div>
        </section>

        <section className="panel stack">
          <div className="eyebrow">Activity counts</div>
          <div className="card-list">
            {Object.entries(analytics.activity_counts).map(([key, value]) => (
              <div className="card" key={key}>
                <strong>{key}</strong>
                <div className="meta">
                  <span>{value}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <ProtectedRoute>
      <AnalyticsPageContent />
    </ProtectedRoute>
  );
}
