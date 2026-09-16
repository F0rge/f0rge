"use client";

import { Button, InlineNotification, PasswordInput, Stack, TextInput, Theme } from "@carbon/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, getBranding, login, type WorkspaceBranding } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, refreshUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [branding, setBranding] = useState<WorkspaceBranding | null>(null);
  const [missingWorkspace, setMissingWorkspace] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    let cancelled = false;
    void getBranding()
      .then((data) => {
        if (cancelled) return;
        setBranding(data);
        document.title = data.display_name;
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setMissingWorkspace(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      await refreshUser();
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid email or password.");
      } else {
        setError(err instanceof Error ? err.message : "Login failed.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const company = branding?.display_name || "your workspace";

  return (
    <Theme theme="g10">
      <div className="vellano-login-page">
        <section className="vellano-login-card">
          <Stack gap={6}>
            <div>
              <h1 className="cds--type-productive-heading-04">Log in</h1>
              <p className="cds--type-body-01">Sign in to {company}.</p>
            </div>
            {missingWorkspace ? (
              <InlineNotification
                kind="error"
                title="No workspace at this address."
                subtitle="Check the hostname or create a company from the public site."
                hideCloseButton
                lowContrast
              />
            ) : null}
            {error ? (
              <InlineNotification
                kind="error"
                title="Login failed"
                subtitle={error}
                hideCloseButton
                lowContrast
              />
            ) : null}
            <form onSubmit={(event) => void onSubmit(event)}>
              <Stack gap={5}>
                <TextInput
                  id="email"
                  labelText="Email"
                  type="email"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  disabled={submitting || missingWorkspace}
                />
                <PasswordInput
                  id="password"
                  labelText="Password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  disabled={submitting || missingWorkspace}
                />
                <Button type="submit" disabled={submitting || missingWorkspace}>
                  Log in
                </Button>
              </Stack>
            </form>
          </Stack>
        </section>
      </div>
    </Theme>
  );
}
