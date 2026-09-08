"use client";

import { Tag } from "@carbon/react";
import Link from "next/link";

import type { NiaCitation } from "@/lib/api";

function isSafeCitation(citation: NiaCitation): boolean {
  const label = citation.label.toLowerCase();
  if (label.includes("openrouter") || label.includes("sk-or-")) {
    return false;
  }
  const href = citation.href?.toLowerCase() ?? "";
  if (href.includes("openrouter")) {
    return false;
  }
  return citation.label.trim().length > 0;
}

type NiaCitationChipsProps = {
  citations?: NiaCitation[];
};

export function NiaCitationChips({ citations }: NiaCitationChipsProps) {
  const safe = (citations ?? []).filter(isSafeCitation);
  if (safe.length === 0) {
    return null;
  }

  return (
    <div className="vellano-nia-citations">
      {safe.map((citation, index) => {
        const key = `${citation.label}-${citation.href ?? index}`;
        const href = citation.href?.trim();
        if (href && href.startsWith("/") && !href.startsWith("//")) {
          return (
            <Link key={key} className="vellano-nia-citations__link" href={href}>
              {citation.label}
            </Link>
          );
        }
        return (
          <Tag key={key} type="gray" size="sm">
            {citation.label}
          </Tag>
        );
      })}
    </div>
  );
}
