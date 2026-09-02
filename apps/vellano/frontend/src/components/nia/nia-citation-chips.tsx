"use client";

import { Button, Tag } from "@carbon/react";
import { useRouter } from "next/navigation";

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
  const router = useRouter();
  const safe = (citations ?? []).filter(isSafeCitation);
  if (safe.length === 0) {
    return null;
  }

  return (
    <div className="vellano-nia-citations">
      {safe.map((citation, index) => {
        const key = `${citation.label}-${citation.href ?? index}`;
        const href = citation.href?.trim();
        if (href) {
          const internal = href.startsWith("/");
          return (
            <Button
              key={key}
              kind="ghost"
              size="sm"
              className="vellano-nia-citations__link"
              onClick={() => {
                if (internal) {
                  router.push(href);
                } else {
                  window.open(href, "_blank", "noopener,noreferrer");
                }
              }}
            >
              {citation.label}
            </Button>
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
