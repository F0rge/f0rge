"use client";

import { InlineNotification, Stack } from "@carbon/react";
import { useEffect } from "react";

import { CanvasSurface } from "@/components/nia/canvas-surface";
import { useAuth } from "@/lib/auth";
import {
  getNiaThread,
  isCanvasSpecPayload,
  listNiaThreads,
} from "@/lib/api";
import { readCanvasSpec, useCanvasSpec, writeCanvasSpec } from "@/lib/nia-canvas-store";
import { canUseNia } from "@/lib/permissions";

const HYDRATE_THREAD_CAP = 10;

async function hydrateCanvasSpecFromThreads(): Promise<boolean> {
  const threads = await listNiaThreads();
  const candidates = threads.slice(0, HYDRATE_THREAD_CAP);
  for (const summary of candidates) {
    const thread = await getNiaThread(summary.id);
    for (let index = thread.messages.length - 1; index >= 0; index -= 1) {
      const payload = thread.messages[index]?.structured_payload;
      if (payload && isCanvasSpecPayload(payload)) {
        writeCanvasSpec(payload);
        return true;
      }
    }
  }
  return false;
}

export default function CanvasPage() {
  const { user } = useAuth();
  const spec = useCanvasSpec();

  useEffect(() => {
    if (readCanvasSpec() || !user || !canUseNia(user)) {
      return;
    }
    void hydrateCanvasSpecFromThreads().catch(() => undefined);
  }, [user]);

  if (!user || !canUseNia(user)) {
    return (
      <section className="vellano-forbidden">
        <InlineNotification
          kind="error"
          title="Not authorized"
          subtitle="You do not have permission to use Nia Canvas."
          hideCloseButton
        />
      </section>
    );
  }

  return (
    <Stack gap={6} className="vellano-page">
      <div>
        <h1 className="cds--type-productive-heading-04">Canvas</h1>
        {spec ? (
          <p className="vellano-muted-text cds--type-body-01">{spec.title}</p>
        ) : (
          <p className="vellano-muted-text cds--type-body-01">
            Ask Nia to chart something — try dining vs sofas this month.
          </p>
        )}
      </div>
      {spec ? <CanvasSurface spec={spec} /> : null}
    </Stack>
  );
}
