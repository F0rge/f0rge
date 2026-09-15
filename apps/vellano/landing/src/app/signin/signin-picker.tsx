"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";

import { Button } from "@/components/button";
import { site, workspaceUrl } from "@/lib/site";
import { checkSlug } from "@/lib/slug";

export function SigninPicker() {
  const id = useId();
  const [value, setValue] = useState("");
  const slug = value.trim().toLowerCase().replace(`.${site.domain}`, "").replace(/^https?:\/\//, "");
  const ok = checkSlug(slug).ok;

  return (
    <form
      className="mt-10 rounded-3xl border border-line bg-white/70 p-6 sm:p-8"
      onSubmit={(e) => {
        e.preventDefault();
        if (ok) window.location.assign(`https://${workspaceUrl(slug)}/login`);
      }}
    >
      <label htmlFor={id} className="block text-sm font-medium">
        Workspace address
      </label>
      <div className="mt-2 flex items-stretch overflow-hidden rounded-xl border border-line bg-white focus-within:border-ink focus-within:shadow-[0_0_0_3px_rgba(22,22,22,.08)]">
        <input
          id={id}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="yourcompany"
          autoCapitalize="none"
          spellCheck={false}
          className="min-w-0 flex-1 bg-transparent px-4 py-3 font-mono text-base outline-none"
        />
        <span className="flex items-center border-l border-line bg-paper px-3 font-mono text-sm text-muted">.{site.domain}</span>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={!ok}>
          Go to login <ArrowRight size={16} />
        </Button>
        <span className="text-sm text-muted">
          No company yet?{" "}
          <Link href="/signup" className="underline decoration-terracotta underline-offset-2">
            Create one
          </Link>
          .
        </span>
      </div>
    </form>
  );
}
