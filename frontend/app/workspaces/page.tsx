import Link from "next/link";

import { apiFetch, demoToken } from "../../lib/api";

type Workspace = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

async function getWorkspaces(): Promise<Workspace[]> {
  if (!demoToken) {
    return [];
  }

  try {
    return await apiFetch<Workspace[]>("/workspaces", { token: demoToken });
  } catch {
    return [];
  }
}

export default async function WorkspacesPage() {
  const workspaces = await getWorkspaces();

  return (
    <div className="panel stack">
      <div className="eyebrow">Workspace dashboard</div>
      <h2>Team workspaces</h2>
      <p className="muted">
        Each workspace bundles members, projects, reports, comments, and learning
        progress in one place, and now also tracks invites, knowledge documents,
        exports, and analytics.
      </p>

      {workspaces.length === 0 ? (
        <div className="empty">
          No workspace data loaded yet. Set `NEXT_PUBLIC_DEMO_TOKEN` after
          registering through the backend API to turn this into a live dashboard.
        </div>
      ) : (
        <div className="card-list">
          {workspaces.map((workspace) => (
            <Link
              className="card"
              href={`/workspaces/${workspace.id}`}
              key={workspace.id}
            >
              <h3>{workspace.name}</h3>
              <p className="muted">
                {workspace.description || "Collaborative research and learning workspace"}
              </p>
              <div className="meta">
                <span>Created {new Date(workspace.created_at).toLocaleString()}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
