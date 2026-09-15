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
  verifying: "Confirming your email",
  database: "Creating your own database",
  migrating: "Laying out the tables",
  seeding: "Adding your owner login and chart of accounts",
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
        <h1 className="mt-4 text-4xl leading-[1.02] sm:text-5xl">That link is not valid.</h1>
        <p className="mt-5 text-lg text-muted">It may have expired or already been used. Links last 24 hours.</p>
        <div className="mt-8 flex gap-3">
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
      <h1 className="mt-4 text-4xl leading-[1.02] sm:text-5xl">
        {done ? (
          <>
            Your workspace is <span className="display-italic">ready.</span>
          </>
        ) : (
          <>
            Setting up <span className="display-italic">your workspace.</span>
          </>
        )}
      </h1>
      <ol className="mt-10 space-y-3" aria-live="polite">
        {order.map((s) => {
          const idx = order.indexOf(s);
          const cur = order.indexOf(stage as Step);
          const state = idx < cur || done ? "done" : idx === cur ? "active" : "todo";
          return (
            <li key={s} className={`flex items-center gap-4 rounded-xl border px-4 py-3 ${state === "active" ? "border-ink bg-white" : "border-line bg-white/50"}`}>
              <span className="grid h-6 w-6 place-items-center rounded-full border border-line bg-paper text-ink">
                {state === "done" ? <Check size={14} className="text-moss" /> : state === "active" ? <Loader2 size={14} className="animate-spin" /> : null}
              </span>
              <span className={state === "todo" ? "text-muted" : ""}>{copy[s]}</span>
            </li>
          );
        })}
      </ol>
      <div className={`mt-10 transition-opacity duration-500 ${done ? "opacity-100" : "opacity-0"}`} aria-hidden={!done}>
        <div className="rounded-2xl border border-line bg-white/70 p-6">
          <p className="text-sm text-muted">Your address</p>
          <p className="mt-1 font-mono text-lg">
            https://<span className="text-terracotta">{workspaceUrl(slug)}</span>
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <ButtonLink href="/signup" aria-disabled className="pointer-events-none opacity-60" tabIndex={-1}>
              Open your workspace
            </ButtonLink>
            <span className="text-xs text-muted">Preview only — provisioning is wired to the real API in the next issue.</span>
          </div>
          <p className="mt-5 text-xs leading-relaxed text-muted">
            The workspace is empty. Sign in with the email and password you chose. Trade portal and Nia are on from day one. Questions:{" "}
            {site.supportEmail}.
          </p>
        </div>
      </div>
    </>
  );
}
