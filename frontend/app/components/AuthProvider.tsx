"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setTokens } from "../lib/api";
import type { User } from "../types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (payload: {
    email: string;
    password: string;
    full_name: string;
  }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const current = await api<User>("/api/auth/me", {}, true);
      setUser(current);
    } catch {
      setTokens(null, null);
      setUser(null);
    }
  };

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const token = await api<{ access_token: string; refresh_token: string }>("/api/auth/login", {
      method: "POST",
      body: form,
    });
    setTokens(token.access_token, token.refresh_token);
    const current = await api<User>("/api/auth/me", {}, true);
    setUser(current);
    return current;
  };

  const register = async (payload: {
    email: string;
    password: string;
    full_name: string;
  }) => {
    await api<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  };

  const logout = () => {
    setTokens(null, null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refreshUser }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
