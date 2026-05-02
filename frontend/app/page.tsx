"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "../components/auth-provider";

export default function HomePage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user) {
      router.replace("/workspaces");
    }
  }, [loading, router, user]);

  if (loading) {
    return <div className="panel empty">Loading the workspace app...</div>;
  }

  if (user) {
    return <div className="panel empty">Opening your workspaces...</div>;
  }

  return (
    <div className="page-stack">
      <section className="hero-card">
        <div className="eyebrow">Research to mastery</div>
        <h2>Run the full product from the browser, not from Swagger.</h2>
        <p className="muted hero-copy">
          Sign in to create workspaces, launch research or learning runs, review
          cited reports, submit checkpoints, manage knowledge, and track exports
          and analytics in one place.
        </p>
        <div className="chip-row">
          <span className="chip">Real auth</span>
          <span className="chip">Live workspace dashboards</span>
          <span className="chip">Project run launcher</span>
          <span className="chip">Exports + jobs</span>
          <span className="chip">Knowledge retrieval</span>
        </div>
        <div className="cta-row">
          <Link className="button primary" href="/register">
            Create account
          </Link>
          <Link className="button secondary" href="/login">
            Login
          </Link>
        </div>
      </section>

      <div className="grid cols-3">
        <section className="panel stack">
          <div className="eyebrow">1. Organize</div>
          <h3>Workspaces and projects</h3>
          <p className="muted">
            Create team workspaces, add projects, invite collaborators, and keep
            reports, comments, and knowledge assets tied to the right context.
          </p>
        </section>
        <section className="panel stack">
          <div className="eyebrow">2. Run</div>
          <h3>Copilot execution</h3>
          <p className="muted">
            Launch `research`, `learn`, or `research_then_learn`, then jump
            directly into the resulting report or learning session.
          </p>
        </section>
        <section className="panel stack">
          <div className="eyebrow">3. Improve</div>
          <h3>Mastery and exports</h3>
          <p className="muted">
            Review checkpoints, source quality, workspace analytics, and export
            artifacts without leaving the product UI.
          </p>
        </section>
      </div>
    </div>
  );
}
