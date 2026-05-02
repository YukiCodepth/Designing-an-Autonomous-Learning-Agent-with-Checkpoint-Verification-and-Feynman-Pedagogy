export default function LoginPage() {
  return (
    <div className="grid cols-2">
      <section className="panel stack">
        <div className="eyebrow">Authentication</div>
        <h2>Product auth screens</h2>
        <p className="muted">
          The backend now supports registration and login with JWT sessions.
          This page is intentionally lightweight so the API contract stays the
          source of truth while the frontend grows.
        </p>
        <div className="card">
          <h3>POST /auth/register</h3>
          <p className="muted">
            Creates a user and a personal workspace in one step.
          </p>
        </div>
        <div className="card">
          <h3>POST /auth/login</h3>
          <p className="muted">
            Returns a bearer token plus the default workspace for dashboard entry.
          </p>
        </div>
      </section>
      <section className="panel stack">
        <div className="eyebrow">Dev setup</div>
        <p className="muted">
          Set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI service and optionally
          set `NEXT_PUBLIC_DEMO_TOKEN` for read-only dashboard fetching while
          the interactive auth flow is being polished.
        </p>
        <div className="card code">
          NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001{"\n"}
          NEXT_PUBLIC_DEMO_TOKEN=&lt;jwt token&gt;
        </div>
      </section>
    </div>
  );
}
