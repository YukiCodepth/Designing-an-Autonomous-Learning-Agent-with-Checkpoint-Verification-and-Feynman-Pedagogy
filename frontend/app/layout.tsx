import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Deep Research Copilot",
  description: "Research, learning, and mastery tracking for teams.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="hero" style={{ marginBottom: 24 }}>
            <div className="eyebrow">Product V2</div>
            <h1 style={{ marginBottom: 8 }}>Deep Research Copilot</h1>
            <p className="muted" style={{ maxWidth: 760 }}>
              A multi-user workspace for source-grounded research, cited reports,
              adaptive learning checkpoints, and collaborative progress tracking.
            </p>
            <div className="cta-row">
              <Link className="button primary" href="/">
                Overview
              </Link>
              <Link className="button secondary" href="/login">
                Auth Screens
              </Link>
              <Link className="button secondary" href="/workspaces">
                Workspace Dashboard
              </Link>
              <Link className="button secondary" href="/analytics/demo">
                Analytics View
              </Link>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
