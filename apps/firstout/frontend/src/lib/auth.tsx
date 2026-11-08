"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, getMe, logout as apiLogout, portalLogout, type AuthUser } from "@/lib/api";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  logout: (redirectUrl?: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, onSignOut, loadIdentity = true }: { children: React.ReactNode; onSignOut: (redirectUrl?: string) => Promise<unknown>; loadIdentity?: boolean }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(loadIdentity);

  const refreshUser = useCallback(async () => {
    if (!loadIdentity) return;
    try {
      const me = await getMe();
      setUser(me);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        return;
      }
      setUser(null);
    }
  }, [loadIdentity]);

  useEffect(() => {
    if (!loadIdentity) return;
    let cancelled = false;

    async function loadSession() {
      try {
        const me = await getMe();
        if (!cancelled) {
          setUser(me);
        }
      } catch {
        if (!cancelled) {
          setUser(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadSession();

    return () => {
      cancelled = true;
    };
  }, [loadIdentity]);

  const logout = useCallback(async (redirectUrl?: string) => {
    // Cookie cleanup cannot delay or prevent the actual Clerk session sign-out.
    void Promise.allSettled([apiLogout(), portalLogout()]);
    await onSignOut(redirectUrl);
    setUser(null);
  }, [onSignOut]);

  const value = useMemo(
    () => ({ user, loading, refreshUser, logout }),
    [user, loading, refreshUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
