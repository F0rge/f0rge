"use client";

import { useState } from "react";
import { Show, SignInButton, SignUpButton, useClerk } from "@clerk/nextjs";
import { Button } from "@f0rge/ui";
import { useRouter } from "next/navigation";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { logoutCustomer } from "@/lib/customer-logout";

export function HeaderAuth() {
  const { signOut } = useClerk();
  const { resetIdentity } = useStorefrontAnalytics();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function logout() {
    setBusy(true); setError("");
    try {
      await logoutCustomer({ resetIdentity, signOut, refresh: () => router.refresh() });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not end your customer session");
      setBusy(false);
    }
  }

  return (
    <>
      <Show when="signed-out">
        <SignInButton mode="redirect">
          <Button type="button" className="header-auth" variant="ghost">Sign in</Button>
        </SignInButton>
        <SignUpButton mode="redirect">
          <Button type="button" className="header-auth" variant="ghost">Sign up</Button>
        </SignUpButton>
      </Show>
      <Show when="signed-in">
        <Button type="button" className="header-auth" disabled={busy} onClick={() => void logout()}>Sign out</Button>
      </Show>
      {error && <p role="alert" className="account-error">{error}</p>}
    </>
  );
}
