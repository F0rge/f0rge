"use client";

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
      className="mt-10 border border-line bg-white p-6 sm:p-8"
      onSubmit={(e) => {
        e.preventDefault();
        if (ok) window.location.assign(`https://${workspaceUrl(slug)}/login`);
      }}
    >
      <label htmlFor={id} className="block text-sm">
        Company hostname
      </label>
      <div className="mt-2 flex h-10 items-stretch bg-paper-2 focus-within:shadow-[inset_0_-2px_0_0_#0f62fe]">
        <input
          id={id}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="yourcompany"
          autoCapitalize="none"
          spellCheck={false}
          className="min-w-0 flex-1 bg-transparent px-4 text-sm outline-none"
        />
        <span className="flex items-center border-l border-line px-3 font-mono text-sm text-muted">.{site.domain}</span>
      </div>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <Button type="submit" disabled={!ok}>
          Go to login
        </Button>
        <span className="text-sm text-muted">
          No company yet?{" "}
          <Link href="/signup" className="text-interactive underline-offset-2 hover:underline">
            Create one
          </Link>
          .
        </span>
      </div>
    </form>
  );
}
