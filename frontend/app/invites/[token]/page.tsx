export default async function InvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;

  return (
    <div className="grid cols-2">
      <section className="panel stack">
        <div className="eyebrow">Invite</div>
        <h2>Workspace invitation</h2>
        <p className="muted">
          This route is the handoff point for the signed workspace invite flow.
          To accept it, sign in through the backend and send this token to
          `POST /auth/accept-invite`.
        </p>
        <div className="card code">{token}</div>
      </section>
      <section className="panel stack">
        <div className="eyebrow">API flow</div>
        <div className="card">
          <h3>1. Authenticate</h3>
          <p className="muted">Use `POST /auth/login` or `POST /auth/register`.</p>
        </div>
        <div className="card">
          <h3>2. Accept invite</h3>
          <p className="muted">
            Call `POST /auth/accept-invite` with <code>{`{ "token": "..." }`}</code> and the
            current user will be added to the workspace.
          </p>
        </div>
      </section>
    </div>
  );
}
