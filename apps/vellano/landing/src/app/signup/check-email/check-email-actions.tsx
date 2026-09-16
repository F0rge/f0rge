"use client";

import { useState } from "react";

import { Button } from "@/components/button";
import { resendSignup } from "@/lib/platform";

export function CheckEmailActions({ signupId }: { signupId: string }) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onResend() {
    if (!signupId || busy) {
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const res = await resendSignup(signupId);
      if (res.ok) {
        setMessage("We sent another link.");
      } else {
        setMessage("Could not resend yet. Wait a minute and try again.");
      }
    } catch {
      setMessage("Network error. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-3">
      <Button type="button" variant="secondary" disabled={!signupId || busy} onClick={() => void onResend()}>
        Resend link
      </Button>
      {message ? <p className="text-sm text-ink">{message}</p> : null}
    </div>
  );
}
