"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ProtectedRoute } from "../../../components/protected-route";
import { useAuth } from "../../../components/auth-provider";
import {
  apiFetch,
  downloadJobArtifact,
  formatApiError,
  pollJobUntilSettled,
} from "../../../lib/api";
import type { BackgroundJob, Project, WorkspaceDetail, WorkspaceInvite } from "../../../lib/types";

function WorkspaceDetailContent() {
  const { token } = useAuth();
  const params = useParams<{ workspaceId: string }>();
  const router = useRouter();
  const workspaceId = params.workspaceId;

  const [detail, setDetail] = useState<WorkspaceDetail | null>(null);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"owner" | "member">("member");
  const [inviteState, setInviteState] = useState<string | null>(null);

  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projectAssignedUserId, setProjectAssignedUserId] = useState("");
  const [projectState, setProjectState] = useState<string | null>(null);

  const [exportState, setExportState] = useState<string | null>(null);

  async function loadWorkspace() {
    if (!token) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [workspaceDetail, workspaceJobs] = await Promise.all([
        apiFetch<WorkspaceDetail>(`/workspaces/${workspaceId}`, { token }),
        apiFetch<BackgroundJob[]>(`/workspaces/${workspaceId}/jobs`, { token }),
      ]);

      setDetail(workspaceDetail);
      setJobs(workspaceJobs);
    } catch (loadError) {
      setError(formatApiError(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadWorkspace();
  }, [token, workspaceId]);

  const ownerMembers = useMemo(
    () => detail?.members.filter((member) => member.role === "owner") ?? [],
    [detail],
  );

  async function handleCreateInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setInviteState("Creating invite...");

    try {
      const invite = await apiFetch<WorkspaceInvite>(`/workspaces/${workspaceId}/invites`, {
        method: "POST",
        token,
        body: {
          email: inviteEmail,
          role: inviteRole,
        },
      });
      setDetail((current) =>
        current
          ? {
              ...current,
              pending_invites: [invite, ...current.pending_invites],
            }
          : current,
      );
      setInviteEmail("");
      setInviteRole("member");
      setInviteState("Invite created successfully.");
    } catch (inviteError) {
      setInviteState(formatApiError(inviteError));
    }
  }

  async function handleCreateProject(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setProjectState("Creating project...");

    try {
      const project = await apiFetch<Project>("/projects", {
        method: "POST",
        token,
        body: {
          workspace_id: workspaceId,
          name: projectName,
          description: projectDescription || null,
          assigned_user_id: projectAssignedUserId || null,
        },
      });
      setDetail((current) =>
        current
          ? {
              ...current,
              projects: [project, ...current.projects],
            }
          : current,
      );
      setProjectName("");
      setProjectDescription("");
      setProjectAssignedUserId("");
      setProjectState("Project created. Opening project hub...");
      router.push(`/workspaces/${workspaceId}/projects/${project.id}`);
    } catch (projectError) {
      setProjectState(formatApiError(projectError));
    }
  }

  async function handleExportWorkspace() {
    if (!token) {
      return;
    }

    setExportState("Queueing workspace summary export...");

    try {
      const job = await apiFetch<BackgroundJob>(`/workspaces/${workspaceId}/exports/summary`, {
        method: "POST",
        token,
      });
      const settledJob = await pollJobUntilSettled<BackgroundJob>(`/jobs/${job.id}`, token);
      setJobs((current) => [settledJob, ...current.filter((item) => item.id !== settledJob.id)]);
      if (settledJob.status === "completed") {
        await downloadJobArtifact(settledJob.id, token, "workspace-summary.md");
        setExportState("Workspace summary exported.");
      } else {
        setExportState(settledJob.error_message || "Workspace export failed.");
      }
    } catch (exportError) {
      setExportState(formatApiError(exportError));
    }
  }

  if (loading) {
    return <div className="panel empty">Loading workspace dashboard...</div>;
  }

  if (error || !detail) {
    return <div className="notice error">{error || "Workspace data is unavailable."}</div>;
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Workspace</div>
            <h2>{detail.workspace.name}</h2>
            <p className="muted">{detail.workspace.description || "No description yet."}</p>
          </div>
          <div className="chip-row">
            <span className="chip">{detail.projects.length} projects</span>
            <span className="chip">{detail.pending_invites.length} pending invites</span>
            <span className="chip">{jobs.length} jobs</span>
          </div>
        </div>
        <div className="cta-row">
          <button className="button secondary" onClick={() => void loadWorkspace()} type="button">
            Refresh
          </button>
          <button className="button primary" onClick={() => void handleExportWorkspace()} type="button">
            Export workspace summary
          </button>
          <Link className="button secondary" href={`/analytics/${workspaceId}`}>
            Open analytics
          </Link>
        </div>
        {exportState ? <div className="notice success">{exportState}</div> : null}
      </section>

      <div className="layout-2">
        <section className="panel stack">
          <div className="eyebrow">Projects</div>
          <div className="card-list">
            {detail.projects.map((project) => (
              <Link
                className="card interactive-card"
                href={`/workspaces/${workspaceId}/projects/${project.id}`}
                key={project.id}
              >
                <h3>{project.name}</h3>
                <p className="muted">{project.description || "No description yet."}</p>
                <div className="meta">
                  <span>Assigned to {project.assigned_user_id || "unassigned"}</span>
                  <span>{new Date(project.created_at).toLocaleString()}</span>
                </div>
              </Link>
            ))}
          </div>

          <form className="form-stack form-card" onSubmit={handleCreateProject}>
            <h3>Create project</h3>
            <label className="field">
              <span>Name</span>
              <input
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="Learning Agent MVP"
                required
                value={projectName}
              />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea
                onChange={(event) => setProjectDescription(event.target.value)}
                placeholder="Short project brief"
                rows={4}
                value={projectDescription}
              />
            </label>
            <label className="field">
              <span>Assigned user ID</span>
              <input
                onChange={(event) => setProjectAssignedUserId(event.target.value)}
                placeholder="Optional user id"
                value={projectAssignedUserId}
              />
            </label>
            {projectState ? <div className="notice info">{projectState}</div> : null}
            <button className="button primary" type="submit">
              Create project
            </button>
          </form>
        </section>

        <aside className="stack">
          <section className="panel stack">
            <div className="eyebrow">Members</div>
            <div className="card-list">
              {detail.members.map((member) => (
                <div className="card" key={member.id}>
                  <strong>{member.user_id}</strong>
                  <div className="meta">
                    <span>{member.role}</span>
                    <span>{new Date(member.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
            {ownerMembers.length > 0 ? (
              <div className="muted">Owners: {ownerMembers.map((member) => member.user_id).join(", ")}</div>
            ) : null}
          </section>

          <section className="panel stack">
            <div className="eyebrow">Invites</div>
            <form className="form-stack" onSubmit={handleCreateInvite}>
              <label className="field">
                <span>Email</span>
                <input
                  onChange={(event) => setInviteEmail(event.target.value)}
                  placeholder="collaborator@example.com"
                  required
                  type="email"
                  value={inviteEmail}
                />
              </label>
              <label className="field">
                <span>Role</span>
                <select onChange={(event) => setInviteRole(event.target.value as "owner" | "member")} value={inviteRole}>
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
              </label>
              {inviteState ? <div className="notice info">{inviteState}</div> : null}
              <button className="button primary" type="submit">
                Create invite
              </button>
            </form>
            <div className="card-list">
              {detail.pending_invites.map((invite) => (
                <div className="card" key={invite.id}>
                  <strong>{invite.email}</strong>
                  <div className="meta">
                    <span>{invite.role}</span>
                    <span>{invite.status}</span>
                  </div>
                  {invite.invite_url ? (
                    <a className="button secondary inline-button" href={invite.invite_url}>
                      Open invite
                    </a>
                  ) : null}
                </div>
              ))}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Jobs</div>
            <div className="card-list">
              {jobs.length === 0 ? (
                <div className="empty">No background jobs yet.</div>
              ) : (
                jobs.map((job) => (
                  <div className="card" key={job.id}>
                    <strong>{job.job_type}</strong>
                    <div className="meta">
                      <span>{job.status}</span>
                      <span>{new Date(job.created_at).toLocaleString()}</span>
                    </div>
                    {job.error_message ? <div className="notice error">{job.error_message}</div> : null}
                    {job.artifact_path ? (
                      <button
                        className="button secondary inline-button"
                        onClick={() => token && downloadJobArtifact(job.id, token)}
                        type="button"
                      >
                        Download artifact
                      </button>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="panel stack">
            <div className="eyebrow">Activity</div>
            <div className="card-list">
              {detail.activity.map((activity) => (
                <div className="card" key={activity.entity_id}>
                  <strong>{activity.title}</strong>
                  <div className="meta">
                    <span>{activity.kind}</span>
                    <span>{new Date(activity.created_at).toLocaleString()}</span>
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

export default function WorkspaceDetailPage() {
  return (
    <ProtectedRoute>
      <WorkspaceDetailContent />
    </ProtectedRoute>
  );
}
