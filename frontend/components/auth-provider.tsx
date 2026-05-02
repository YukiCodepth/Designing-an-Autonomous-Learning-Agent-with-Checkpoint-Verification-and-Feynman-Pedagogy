"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiFetch } from "../lib/api";
import type { TokenResponse, User } from "../lib/types";

const AUTH_TOKEN_KEY = "deep-research-copilot-token";

type AuthContextValue = {
  token: string | null;
  user: User | null;
  loading: boolean;
  loginWithTokenResponse: (payload: TokenResponse) => void;
  restoreSession: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const restoreSession = useCallback(async () => {
    const storedToken = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!storedToken) {
      setLoading(false);
      return;
    }

    try {
      const currentUser = await apiFetch<User>("/auth/me", { token: storedToken });
      setToken(storedToken);
      setUser(currentUser);
    } catch {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  const loginWithTokenResponse = useCallback((payload: TokenResponse) => {
    localStorage.setItem(AUTH_TOKEN_KEY, payload.access_token);
    setToken(payload.access_token);
    setUser(payload.user);
    setLoading(false);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      user,
      loading,
      loginWithTokenResponse,
      restoreSession,
      logout,
    }),
    [token, user, loading, loginWithTokenResponse, restoreSession, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
