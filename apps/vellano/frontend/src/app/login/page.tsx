"use client";

import { Button, InlineNotification, PasswordInput, Stack, TextInput, Theme } from "@carbon/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, login } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, refreshUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

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

  return (
    <Theme theme="g10">
      <div className="vellano-login-page">
        <section className="vellano-login-card">
          <Stack gap={6}>
            <div>
              <h1 className="cds--type-productive-heading-04">Log in</h1>
              <p className="cds--type-body-01">Sign in to the Vellano back office.</p>
            </div>
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
                  disabled={submitting}
                />
                <PasswordInput
                  id="password"
                  labelText="Password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  disabled={submitting}
                />
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Signing in…" : "Log in"}
                </Button>
              </Stack>
            </form>
          </Stack>
        </section>
      </div>
    </Theme>
  );
}
