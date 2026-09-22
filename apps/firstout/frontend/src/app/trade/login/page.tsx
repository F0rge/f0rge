"use client";

import { Button, InlineNotification, PasswordInput, Stack, TextInput, Theme } from "@carbon/react";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, getPortalMe, portalLogin } from "@/lib/api";

export default function TradeLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    void getPortalMe()
      .then(() => router.replace("/trade/catalogue"))
      .catch(() => undefined);
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await portalLogin(email, password);
      router.push("/trade/catalogue");
    } catch (err) {
      setError(err instanceof ApiError ? "Invalid email or password." : "Login failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Theme theme="g10">
      <main style={{ maxWidth: "24rem", margin: "4rem auto", padding: "1rem" }}>
        <Stack gap={5}>
          <h1>Trade portal</h1>
          {error ? <InlineNotification kind="error" title={error} hideCloseButton /> : null}
          <form onSubmit={(event) => void onSubmit(event)}>
            <Stack gap={4}>
              <TextInput
                id="trade-email"
                labelText="Email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <PasswordInput
                id="trade-password"
                labelText="Password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <Button type="submit" disabled={submitting}>
                Sign in
              </Button>
            </Stack>
          </form>
        </Stack>
      </main>
    </Theme>
  );
}
