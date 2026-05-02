import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "../components/app-shell";
import { AuthProvider } from "../components/auth-provider";

export const metadata: Metadata = {
  title: "Deep Research Copilot",
  description: "Research, learning, and mastery tracking for teams.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
