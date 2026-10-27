"use client";

import { Button, InlineNotification, PasswordInput, Stack, Theme } from "@carbon/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { ApiError, confirmPasswordReset } from "@/lib/api";

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(token ? null : "This reset link is invalid.");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("This reset link is invalid.");
      return;
    }
    if (password !== passwordConfirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await confirmPasswordReset(token, password, passwordConfirm);
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reset the password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Theme theme="g10">
      <div className="firstout-login-page">
        <section className="firstout-login-card">
          <Stack gap={6}>
            <div>
              <img className="firstout-login-mark" src="/brand/logo-transparent.png" alt="Firstout" width={72} height={72} />
              <h1 className="cds--type-productive-heading-04">Choose a new password</h1>
              <p className="cds--type-body-01">Use at least 8 characters. This link works once.</p>
            </div>
            {message ? (
              <InlineNotification
                kind="success"
                title="Password updated"
                subtitle={message}
                hideCloseButton
                lowContrast
              />
            ) : null}
            {error ? (
              <InlineNotification
                kind="error"
                title="Could not reset password"
                subtitle={error}
                hideCloseButton
                lowContrast
              />
            ) : null}
            {message ? (
              <Link href="/login" className="cds--link">
                Log in
              </Link>
            ) : (
              <form onSubmit={(event) => void onSubmit(event)}>
                <Stack gap={5}>
                  <PasswordInput
                    id="password"
                    labelText="New password"
                    autoComplete="new-password"
                    helperText="At least 8 characters."
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    disabled={submitting || !token}
                  />
                  <PasswordInput
                    id="password-confirm"
                    labelText="Confirm password"
                    autoComplete="new-password"
                    value={passwordConfirm}
                    onChange={(event) => setPasswordConfirm(event.target.value)}
                    required
                    disabled={submitting || !token}
                  />
                  <Button type="submit" disabled={submitting || !token}>
                    {submitting ? "Saving…" : "Update password"}
                  </Button>
                  <Link href="/login" className="cds--link">
                    Back to log in
                  </Link>
                </Stack>
              </form>
            )}
          </Stack>
        </section>
      </div>
    </Theme>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
