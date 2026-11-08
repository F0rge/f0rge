"use client";

import { Button, InlineNotification, Loading, Stack } from "@carbon/react";
import { useAuth as useClerkAuth, useUser } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, acceptPortalInvitation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ClerkAccountButton } from "@/components/clerk-account-button";
import {
  clearPortalInvitation, invitationTokenFromHash, portalAccessUrl,
  readPortalInvitation, rememberPortalInvitation, tradeAuthUrl,
} from "@/lib/trade-auth";

export default function AcceptTradeInvitationPage() {
  const { isLoaded, isSignedIn } = useClerkAuth();
  const { user } = useUser();
  const { logout } = useAuth();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fragmentToken = invitationTokenFromHash(window.location.hash);
    let pendingToken = fragmentToken;
    try {
      if (fragmentToken) rememberPortalInvitation(window.sessionStorage, fragmentToken);
      pendingToken ??= readPortalInvitation(window.sessionStorage);
    } catch {
      setError("This browser cannot keep the invitation during sign-in. Sign in, then reopen the original invitation link.");
    }
    if (window.location.hash) window.history.replaceState(window.history.state, "", "/trade/accept-invitation");
    setToken(pendingToken); setReady(true);
  }, []);

  async function accept() {
    if (!token) return;
    setSaving(true); setError(null);
    try {
      const access = await acceptPortalInvitation(token);
      try { clearPortalInvitation(window.sessionStorage); } catch { /* Acceptance already consumed the one-use invitation. */ }
      setToken(null);
      router.replace(portalAccessUrl(access.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        try { clearPortalInvitation(window.sessionStorage); } catch { /* No persistent fallback. */ }
        setToken(null);
      }
      setError(err instanceof Error ? err.message : "Could not accept the invitation.");
    } finally { setSaving(false); }
  }

  if (!ready || !isLoaded) return <Loading withOverlay={false} description="Loading invitation…" />;
  return <main className="firstout-onboarding-page"><section className="firstout-onboarding-content"><Stack gap={5}>
    <h1 className="cds--type-productive-heading-04">Accept trade invitation</h1>
    {error ? <InlineNotification kind="error" title="Invitation" subtitle={error} hideCloseButton /> : null}
    {!token ? <p>Open the original invitation link, or ask the business for a new one. Invitation links expire and can be used once.</p> : !isSignedIn ? <>
      <p>Sign in or create your Clerk account with the invited email, then return here to accept access.</p>
      <Button href={tradeAuthUrl("login", "/trade/accept-invitation")}>Sign in</Button>
      <Button kind="tertiary" href={tradeAuthUrl("sign-up", "/trade/accept-invitation")}>Create an account</Button>
    </> : <>
      <p>Accept using {user?.primaryEmailAddress?.emailAddress}. Only the verified invited account can accept this link.</p>
      <Button disabled={saving} onClick={() => void accept()}>{saving ? "Accepting…" : "Accept invitation"}</Button>
      <ClerkAccountButton />
      <Button kind="ghost" disabled={saving} onClick={() => void logout(tradeAuthUrl("login", "/trade/accept-invitation")).then(() => router.replace(tradeAuthUrl("login", "/trade/accept-invitation")))}>Use another account</Button>
    </>}
    <Button kind="ghost" href="/trade/catalogue">Your trade accounts</Button>
  </Stack></section></main>;
}
