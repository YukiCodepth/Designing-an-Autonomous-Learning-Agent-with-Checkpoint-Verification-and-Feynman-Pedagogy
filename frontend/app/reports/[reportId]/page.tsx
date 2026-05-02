import Link from "next/link";

import { apiFetch, demoToken } from "../../../lib/api";

type Report = {
  id: string;
  title: string;
  executive_summary: string;
  status: string;
  body: string;
  sources: {
    id: string;
    title: string;
    url: string;
    confidence: number;
  }[];
  source_reviews: {
    id: string;
    source_id: string;
    decision: string;
    note: string | null;
  }[];
  sections: {
    id: string;
    heading: string;
    body: string;
    citation_source_ids: string[];
  }[];
};

async function getReport(reportId: string): Promise<Report | null> {
  if (!demoToken) {
    return null;
  }
  try {
    return await apiFetch<Report>(`/reports/${reportId}`, { token: demoToken });
  } catch {
    return null;
  }
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const { reportId } = await params;
  const report = await getReport(reportId);

  if (!report) {
    return (
      <div className="panel empty">
        Report data is unavailable. Run the backend product API and set a demo token
        to turn this viewer live.
      </div>
    );
  }

  return (
    <div className="layout-2">
      <section className="panel stack">
        <div className="eyebrow">Cited report</div>
        <h2>{report.title}</h2>
        <div className="chip-row">
          <span className="chip">Status: {report.status}</span>
          <span className="chip">{report.sources.length} sources</span>
          <span className="chip">{report.source_reviews.length} source reviews</span>
        </div>
        <p className="muted">{report.executive_summary}</p>

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

      <aside className="stack">
        <section className="panel">
          <div className="eyebrow">Sources</div>
          <div className="card-list">
            {report.sources.map((source) => (
              <a
                className="card"
                href={source.url}
                key={source.id}
                target="_blank"
                rel="noreferrer"
              >
                <h3>{source.title}</h3>
                <div className="meta">
                  <span>Confidence {source.confidence}</span>
                </div>
              </a>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="eyebrow">Source review</div>
          <div className="card-list">
            {report.source_reviews.length === 0 ? (
              <div className="empty">
                No source decisions yet. Use `POST /sources/:sourceId/reviews` to mark
                evidence as approved or rejected.
              </div>
            ) : (
              report.source_reviews.map((review) => (
                <div className="card" key={review.id}>
                  <h3>{review.decision}</h3>
                  <p className="muted">{review.note || "No note provided."}</p>
                  <div className="meta">
                    <span>{review.source_id}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
        <section className="panel">
          <div className="eyebrow">Next step</div>
          <p className="muted">
            Launch a learning session through `POST /reports/{report.id}/learn` and
            then open the resulting learning session page. You can also queue
            markdown and PDF exports from the new report export endpoints.
          </p>
          <Link className="button secondary" href="/workspaces">
            Back to dashboard
          </Link>
        </section>
      </aside>
    </div>
  );
}
