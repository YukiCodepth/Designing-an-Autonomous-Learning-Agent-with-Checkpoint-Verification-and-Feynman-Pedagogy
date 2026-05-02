import Link from "next/link";

import { apiFetch, demoToken } from "../../../lib/api";

type ActivityItem = {
  kind: string;
  entity_id: string;
  title: string;
  created_at: string;
};

type Project = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

type Member = {
  id: string;
  user_id: string;
  role: string;
};

type WorkspaceDetail = {
  workspace: {
    id: string;
    name: string;
    description: string | null;
  };
  members: Member[];
  projects: Project[];
  pending_invites: {
    id: string;
    email: string;
    role: string;
    invite_url: string | null;
  }[];
  activity: ActivityItem[];
};

async function getWorkspaceDetail(workspaceId: string): Promise<WorkspaceDetail | null> {
  if (!demoToken) {
    return null;
  }

  try {
    return await apiFetch<WorkspaceDetail>(`/workspaces/${workspaceId}`, {
      token: demoToken,
    });
  } catch {
    return null;
  }
}

export default async function WorkspaceDetailPage({
  params,
}: {
  params: Promise<{ workspaceId: string }>;
}) {
  const { workspaceId } = await params;
  const detail = await getWorkspaceDetail(workspaceId);

  if (!detail) {
    return (
      <div className="panel empty">
        Workspace data is unavailable. Authenticate through the backend and set
        `NEXT_PUBLIC_DEMO_TOKEN` to enable live reads.
      </div>
    );
  }

  return (
    <div className="layout-2">
      <section className="panel stack">
        <div className="eyebrow">Workspace</div>
        <h2>{detail.workspace.name}</h2>
        <p className="muted">
          {detail.workspace.description || "No description yet."}
        </p>
        <div className="chip-row">
          <span className="chip">{detail.members.length} members</span>
          <span className="chip">{detail.projects.length} projects</span>
          <span className="chip">{detail.pending_invites.length} pending invites</span>
          <span className="chip">{detail.activity.length} recent activities</span>
        </div>

        <div className="card-list">
          {detail.projects.map((project) => (
            <Link
              key={project.id}
              href={`/workspaces/${workspaceId}/projects/${project.id}`}
              className="card"
            >
              <h3>{project.name}</h3>
              <p className="muted">{project.description || "No description yet."}</p>
              <div className="meta">
                <span>{new Date(project.created_at).toLocaleString()}</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <aside className="stack">
        <section className="panel">
          <div className="eyebrow">Members</div>
          <div className="card-list">
            {detail.members.map((member) => (
              <div className="card" key={member.id}>
                <h3 style={{ marginBottom: 6 }}>{member.user_id}</h3>
                <p className="muted">{member.role}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="eyebrow">Invites</div>
          <div className="card-list">
            {detail.pending_invites.length === 0 ? (
              <div className="empty">No pending invites.</div>
            ) : (
              detail.pending_invites.map((invite) => (
                <div className="card" key={invite.id}>
                  <h3 style={{ marginBottom: 6 }}>{invite.email}</h3>
                  <p className="muted">{invite.role}</p>
                  {invite.invite_url ? (
                    <a className="muted" href={invite.invite_url}>
                      Invite link
                    </a>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </section>

        <section className="panel">
          <div className="eyebrow">Activity feed</div>
          <div className="card-list">
            {detail.activity.map((item) => (
              <div className="card" key={item.entity_id}>
                <h3 style={{ marginBottom: 6 }}>{item.title}</h3>
                <div className="meta">
                  <span>{item.kind}</span>
                  <span>{new Date(item.created_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="cta-row">
            <Link className="button secondary" href={`/analytics/${workspaceId}`}>
              Open analytics
            </Link>
          </div>
        </section>
      </aside>
    </div>
  );
}
