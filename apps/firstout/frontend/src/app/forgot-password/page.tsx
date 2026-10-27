"use client";

import { Button, InlineNotification, Stack, TextInput, Theme } from "@carbon/react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { ApiError, requestPasswordReset } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    setSubmitting(true);
    try {
      const result = await requestPasswordReset(email);
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send reset instructions.");
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
              <h1 className="cds--type-productive-heading-04">Forgot your password?</h1>
              <p className="cds--type-body-01">
                Enter the email on your Firstout account. If it matches, we will send reset instructions.
              </p>
            </div>
            {message ? (
              <InlineNotification
                kind="success"
                title="Check your email"
                subtitle={message}
                hideCloseButton
                lowContrast
              />
            ) : null}
            {error ? (
              <InlineNotification
                kind="error"
                title="Could not continue"
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
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Sending…" : "Send reset link"}
                </Button>
                <Link href="/login" className="cds--link">
                  Back to log in
                </Link>
              </Stack>
            </form>
          </Stack>
        </section>
      </div>
    </Theme>
  );
}
