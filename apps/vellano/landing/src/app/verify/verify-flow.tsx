"use client";

import { Check, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/button";
import { signupStatus, verifySignup } from "@/lib/platform";
import { loginHrefFromWorkspaceOrigin, site } from "@/lib/site";
import {
  GENERIC_PROVISION_FAILURE,
  POLL_INTERVAL_MS,
  POLL_MAX_MS,
  stepState,
  uiFromSignupStatus,
  type ProvisionStep,
  type ProvisionUi,
} from "@/lib/signup-status";

const order: ProvisionStep[] = ["verifying", "database", "migrating", "seeding", "ready"];

const copy: Record<ProvisionStep, string> = {
  verifying: "Confirming the email",
  database: "CREATE DATABASE and role",
  migrating: "alembic upgrade head",
  seeding: "Owner user and chart of accounts — no sample locations",
  ready: "Ready",
};

export function VerifyFlow() {
  const params = useSearchParams();
  const token = params.get("token");
  const [ui, setUi] = useState<ProvisionUi>(token ? { kind: "progress", stage: "verifying" } : { kind: "invalid" });

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;
    const started = Date.now();
    let pollTimer: number | undefined;

    async function readStatus(signupId: string): Promise<ProvisionUi | null> {
      const res = await signupStatus(signupId);
      if (!res.ok) {
        return { kind: "failed", message: GENERIC_PROVISION_FAILURE };
      }
      const body = (await res.json()) as {
        status: string;
        workspace_url?: string | null;
        failure?: string | null;
      };
      return uiFromSignupStatus(body.status, body.workspace_url, body.failure);
    }

    async function tick(signupId: string) {
      if (cancelled) {
        return;
      }
      if (Date.now() - started > POLL_MAX_MS) {
        setUi({ kind: "failed", message: GENERIC_PROVISION_FAILURE });
        return;
      }
      try {
        const next = await readStatus(signupId);
        if (cancelled || next === null) {
          return;
        }
        setUi(next);
        if (next.kind !== "progress") {
          return;
        }
        pollTimer = window.setTimeout(() => {
          void tick(signupId);
        }, POLL_INTERVAL_MS);
      } catch {
        if (!cancelled) {
          setUi({ kind: "failed", message: GENERIC_PROVISION_FAILURE });
        }
      }
    }

    async function start() {
      try {
        const res = await verifySignup(token as string);
        if (cancelled) {
          return;
        }
        if (!res.ok) {
          setUi({ kind: "invalid" });
          return;
        }
        const body = (await res.json()) as {
          signup_id: string;
          status: string;
        };
        const next = uiFromSignupStatus(body.status);
        setUi(next);
        if (next.kind !== "progress") {
          return;
        }
        await tick(body.signup_id);
      } catch {
        if (!cancelled) {
          setUi({ kind: "failed", message: GENERIC_PROVISION_FAILURE });
        }
      }
    }

    void start();
    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [token]);

  if (ui.kind === "invalid") {
    return (
      <>
        <p className="eyebrow">Verification</p>
        <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">That link is not valid.</h1>
        <p className="mt-5 text-base text-muted">Expired or already used. Links last 24 hours and work once.</p>
        <div className="mt-8">
          <ButtonLink href="/signup">Start again</ButtonLink>
        </div>
      </>
    );
  }

  if (ui.kind === "failed") {
    return (
      <>
        <p className="eyebrow">Verification</p>
        <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">We could not finish setup.</h1>
        <p className="mt-5 text-base text-muted">{ui.message}</p>
        <p className="mt-3 text-sm text-muted">Questions: {site.supportEmail}.</p>
        <div className="mt-8">
          <ButtonLink href="/signup">Start again</ButtonLink>
        </div>
      </>
    );
  }

  const done = ui.kind === "ready";
  const loginHref = done ? loginHrefFromWorkspaceOrigin(ui.workspaceUrl) : "";

  return (
    <>
      <p className="eyebrow">Step 3 of 3</p>
      <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">{done ? "Workspace ready." : "Provisioning the database."}</h1>
      <ol className="mt-10 border-y border-line" aria-live="polite">
        {order.map((s) => {
          const state = stepState(s, ui);
          return (
            <li key={s} className={`flex items-center gap-4 border-b border-line px-4 py-3 last:border-b-0 ${state === "active" ? "bg-paper-2" : "bg-white"}`}>
              <span className="grid h-6 w-6 place-items-center border border-line text-ink">
                {state === "done" ? <Check size={14} className="text-moss" /> : state === "active" ? <Loader2 size={14} className="animate-spin" /> : null}
              </span>
              <span className={state === "todo" ? "text-muted" : ""}>{copy[s]}</span>
            </li>
          );
        })}
      </ol>
      <div className={`mt-10 transition-opacity duration-500 ${done ? "opacity-100" : "opacity-0"}`} aria-hidden={!done}>
        <div className="border border-line bg-paper-2 p-6">
          <p className="text-sm text-muted">Hostname</p>
          <p className="mt-1 font-mono text-lg">{done ? ui.workspaceUrl : ""}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            {done ? (
              <ButtonLink href={loginHref}>Open workspace</ButtonLink>
            ) : (
              <span className="text-sm text-muted">Waiting for the workspace address.</span>
            )}
          </div>
          <p className="mt-5 text-xs leading-relaxed text-muted">
            Empty catalogue. Sign in with the email and password you chose. Questions: {site.supportEmail}.
          </p>
        </div>
      </div>
    </>
  );
}
