"use client";

import { Button, InlineNotification, Stack } from "@carbon/react";
import { useEffect } from "react";

import { CanvasSurface } from "@/components/nia/canvas-surface";
import { useAuth } from "@/lib/auth";
import { getNiaThread, listNiaThreads } from "@/lib/api";
import {
  bindCanvasUser,
  clearCanvasSpec,
  isCanvasCleared,
  readCanvasSpec,
  useCanvasSpec,
} from "@/lib/nia-canvas-store";
import { isEmptyCanvasSpec } from "@/lib/nia-canvas-types";
import { hydrateCanvasFromThreadMessages } from "@/lib/nia-thread-utils";
import { canUseNia } from "@/lib/permissions";

const HYDRATE_THREAD_CAP = 10;
const EMPTY_COPY =
  "Ask Nia to chart overdue invoices, sales by SKU, or dining vs sofas.";

async function hydrateCanvasSpecFromThreads(): Promise<void> {
  if (readCanvasSpec() || isCanvasCleared()) {
    return;
  }
  const threads = await listNiaThreads();
  const candidates = threads.slice(0, HYDRATE_THREAD_CAP);
  const detailed = await Promise.all(candidates.map((summary) => getNiaThread(summary.id)));
  if (isCanvasCleared()) {
    return;
  }
  hydrateCanvasFromThreadMessages(detailed);
}

export default function CanvasPage() {
  const { user } = useAuth();
  const spec = useCanvasSpec();
  const empty = isEmptyCanvasSpec(spec);

  useEffect(() => {
    if (!user || !canUseNia(user)) {
      return;
    }
    bindCanvasUser(user.id);
    if (readCanvasSpec() || isCanvasCleared()) {
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
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Canvas</h1>
          <p className="vellano-muted-text cds--type-body-01">
            {empty ? EMPTY_COPY : spec?.title}
          </p>
        </div>
        <Button kind="ghost" size="sm" onClick={() => clearCanvasSpec()}>
          Clear canvas
        </Button>
      </div>
      {empty || !spec ? null : <CanvasSurface spec={spec} />}
    </Stack>
  );
}
