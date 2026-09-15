"use client";

import { Check, Loader2 } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/button";
import { site, workspaceUrl } from "@/lib/site";

type Step = "verifying" | "database" | "migrating" | "seeding" | "ready";
type Stage = Step | "invalid";

const order: Step[] = ["verifying", "database", "migrating", "seeding", "ready"];

const copy: Record<Step, string> = {
  verifying: "Confirming the email",
  database: "CREATE DATABASE and role",
  migrating: "alembic upgrade head",
  seeding: "Owner user and chart of accounts — no sample locations",
  ready: "Ready",
};

export function VerifyFlow() {
  const params = useSearchParams();
  const token = params.get("token");
  const [stage, setStage] = useState<Stage>(token ? "verifying" : "invalid");

  useEffect(() => {
    if (stage === "invalid" || stage === "ready") return;
    const next = order[order.indexOf(stage as Step) + 1];
    const t = setTimeout(() => setStage(next), 1100);
    return () => clearTimeout(t);
  }, [stage]);

  if (stage === "invalid") {
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

  const slug = "acme";
  const done = stage === "ready";

  return (
    <>
      <p className="eyebrow">Step 3 of 3</p>
      <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">{done ? "Workspace ready." : "Provisioning the database."}</h1>
      <ol className="mt-10 border-y border-line" aria-live="polite">
        {order.map((s) => {
          const idx = order.indexOf(s);
          const cur = order.indexOf(stage as Step);
          const state = idx < cur || done ? "done" : idx === cur ? "active" : "todo";
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
          <p className="mt-1 font-mono text-lg">https://{workspaceUrl(slug)}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <ButtonLink href="/signup" aria-disabled className="pointer-events-none opacity-50" tabIndex={-1}>
              Open workspace
            </ButtonLink>
            <span className="text-xs text-muted">Preview — live provisioning is the platform API in a later issue.</span>
          </div>
          <p className="mt-5 text-xs leading-relaxed text-muted">
            Empty catalogue. Sign in with the email and password you chose. Questions: {site.supportEmail}.
          </p>
        </div>
      </div>
    </>
  );
}
