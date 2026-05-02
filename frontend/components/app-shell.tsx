"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "./auth-provider";

const protectedLinks = [
  { href: "/workspaces", label: "Workspaces" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="shell-shell">
      <aside className="sidebar">
        <div className="brand-card">
          <div className="eyebrow">Workspace App</div>
          <h1>Deep Research Copilot</h1>
          <p className="muted">
            A real product surface for collaborative research, reports, mastery,
            knowledge retrieval, and export workflows.
          </p>
        </div>

        <nav className="nav-stack">
          {protectedLinks.map((link) => (
            <Link
              className={`nav-link ${pathname?.startsWith(link.href) ? "active" : ""}`}
              href={link.href}
              key={link.href}
            >
              {link.label}
            </Link>
          ))}
          {!user ? (
            <>
              <Link
                className={`nav-link ${pathname === "/login" ? "active" : ""}`}
                href="/login"
              >
                Login
              </Link>
              <Link
                className={`nav-link ${pathname === "/register" ? "active" : ""}`}
                href="/register"
              >
                Register
              </Link>
            </>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          {user ? (
            <div className="account-card">
              <div className="muted small-label">Signed in</div>
              <strong>{user.full_name}</strong>
              <div className="muted">{user.email}</div>
              <button
                className="button secondary"
                onClick={() => {
                  logout();
                  router.push("/login");
                }}
                type="button"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="account-card">
              <div className="muted">
                Sign in to create workspaces, run the copilot, and manage reports.
              </div>
            </div>
          )}
        </div>
      </aside>

      <main className="main-shell">{children}</main>
    </div>
  );
}
