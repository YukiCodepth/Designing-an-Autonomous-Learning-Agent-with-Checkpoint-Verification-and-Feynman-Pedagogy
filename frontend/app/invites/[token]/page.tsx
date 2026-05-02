"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../../components/auth-provider";
import { apiFetch, formatApiError } from "../../../lib/api";
import type { WorkspaceInvite } from "../../../lib/types";

export default function InvitePage() {
  const { token: authToken, user, loading } = useAuth();
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const inviteToken = params.token;

  const [status, setStatus] = useState("Preparing invite flow...");
  const [acceptedWorkspaceId, setAcceptedWorkspaceId] = useState<string | null>(null);

  useEffect(() => {
    async function acceptInvite() {
      if (!authToken || !user) {
        return;
      }

      setStatus("Accepting workspace invite...");

      try {
        const invite = await apiFetch<WorkspaceInvite>("/auth/accept-invite", {
          method: "POST",
          token: authToken,
          body: {
            token: inviteToken,
          },
        });
        setAcceptedWorkspaceId(invite.workspace_id);
        setStatus("Invite accepted. Opening workspace...");
        router.replace(`/workspaces/${invite.workspace_id}`);
      } catch (acceptError) {
        setStatus(formatApiError(acceptError));
      }
    }

    if (!loading && user) {
      void acceptInvite();
    } else if (!loading && !user) {
      setStatus("Sign in or register to accept this workspace invite.");
    }
  }, [authToken, inviteToken, loading, router, user]);

  return (
    <div className="auth-wrap">
      <section className="panel stack auth-panel">
        <div className="eyebrow">Workspace invite</div>
        <h2>Invite acceptance</h2>
        <p className="muted">
          This page now handles the signed invite directly. If you are logged in,
          it will attach you to the workspace automatically.
        </p>
        <div className="card code">{inviteToken}</div>
        <div className="notice info">{status}</div>
        {!user && !loading ? (
          <div className="cta-row">
            <Link className="button primary" href={`/login?next=${encodeURIComponent(`/invites/${inviteToken}`)}`}>
              Login to accept
            </Link>
            <Link className="button secondary" href={`/register?next=${encodeURIComponent(`/invites/${inviteToken}`)}`}>
              Register and accept
            </Link>
          </div>
        ) : null}
        {acceptedWorkspaceId ? (
          <Link className="button secondary" href={`/workspaces/${acceptedWorkspaceId}`}>
            Open accepted workspace
          </Link>
        ) : null}
      </section>
    </div>
  );
}
