"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ProtectedRoute } from "../../components/protected-route";
import { useAuth } from "../../components/auth-provider";
import { apiFetch, formatApiError } from "../../lib/api";
import type { Workspace } from "../../lib/types";

function WorkspaceContent() {
  const { token } = useAuth();
  const router = useRouter();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    async function loadWorkspaces() {
      if (!token) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const response = await apiFetch<Workspace[]>("/workspaces", { token });
        setWorkspaces(response);
      } catch (loadError) {
        setError(formatApiError(loadError));
      } finally {
        setLoading(false);
      }
    }

    void loadWorkspaces();
  }, [token]);

  async function handleCreateWorkspace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const workspace = await apiFetch<Workspace>("/workspaces", {
        method: "POST",
        token,
        body: {
          name,
          description: description || null,
        },
      });
      setWorkspaces((current) => [workspace, ...current]);
      setName("");
      setDescription("");
      router.push(`/workspaces/${workspace.id}`);
    } catch (createError) {
      setError(formatApiError(createError));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="panel stack">
        <div className="eyebrow">Workspace dashboard</div>
        <div className="section-heading">
          <div>
            <h2>Your workspaces</h2>
            <p className="muted">
              Open an existing workspace or create a new one to organize projects,
              runs, reports, jobs, and learning sessions.
            </p>
          </div>
        </div>

        {loading ? <div className="empty">Loading workspace data...</div> : null}
        {error ? <div className="notice error">{error}</div> : null}

        {!loading && workspaces.length === 0 ? (
          <div className="empty">
            No workspaces yet. Create one below and the app will route you straight
            into the live dashboard.
          </div>
        ) : null}

        <div className="card-list">
          {workspaces.map((workspace) => (
            <Link className="card interactive-card" href={`/workspaces/${workspace.id}`} key={workspace.id}>
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
      </section>

      <section className="panel stack">
        <div className="eyebrow">Create workspace</div>
        <h3>Start a new collaboration space</h3>
        <form className="form-stack" onSubmit={handleCreateWorkspace}>
          <label className="field">
            <span>Name</span>
            <input
              onChange={(event) => setName(event.target.value)}
              placeholder="AI Research Team"
              required
              value={name}
            />
          </label>
          <label className="field">
            <span>Description</span>
            <textarea
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this workspace is for"
              rows={4}
              value={description}
            />
          </label>
          <button className="button primary" disabled={creating} type="submit">
            {creating ? "Creating..." : "Create workspace"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default function WorkspacesPage() {
  return (
    <ProtectedRoute>
      <WorkspaceContent />
    </ProtectedRoute>
  );
}
