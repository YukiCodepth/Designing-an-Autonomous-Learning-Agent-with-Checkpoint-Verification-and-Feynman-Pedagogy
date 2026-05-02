"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "../../components/auth-provider";
import { apiFetch, formatApiError } from "../../lib/api";
import type { TokenResponse } from "../../lib/types";

export default function RegisterPage() {
  const { user, loading, loginWithTokenResponse } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next") || "/workspaces";

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) {
      router.replace(next);
    }
  }, [loading, next, router, user]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await apiFetch<TokenResponse>("/auth/register", {
        method: "POST",
        body: {
          email,
          full_name: fullName,
          password,
        },
      });
      loginWithTokenResponse(response);
      router.replace(next);
    } catch (submitError) {
      setError(formatApiError(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-wrap">
      <section className="panel stack auth-panel">
        <div className="eyebrow">Register</div>
        <h2>Create your workspace account</h2>
        <p className="muted">
          Registration creates your user and personal workspace so you can start
          building projects immediately.
        </p>

        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field">
            <span>Full name</span>
            <input
              autoComplete="name"
              onChange={(event) => setFullName(event.target.value)}
              placeholder="Aman Sharma"
              required
              value={fullName}
            />
          </label>

          <label className="field">
            <span>Email</span>
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
              type="email"
              value={email}
            />
          </label>

          <label className="field">
            <span>Password</span>
            <input
              autoComplete="new-password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              required
              type="password"
              value={password}
            />
          </label>

          {error ? <div className="notice error">{error}</div> : null}

          <button className="button primary" disabled={submitting} type="submit">
            {submitting ? "Creating account..." : "Register"}
          </button>
        </form>

        <div className="muted">
          Already have an account? <Link href={`/login?next=${encodeURIComponent(next)}`}>Login</Link>
        </div>
      </section>
    </div>
  );
}
