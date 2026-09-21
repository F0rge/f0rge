"use client";

import { Button, InlineNotification, Stack } from "@carbon/react";
import { DocumentExport } from "@carbon/icons-react";
import { useEffect, useState } from "react";

import { CanvasSurface } from "@/components/nia/canvas-surface";
import { useAuth } from "@/lib/auth";
import { getNiaThread, listNiaThreads } from "@/lib/api";
import {
  bindCanvasUser,
  clearCanvasSpec,
  readCanvasSpec,
  useCanvasSpec,
} from "@/lib/nia-canvas-store";
import { isEmptyCanvasSpec } from "@/lib/nia-canvas-types";
import { canvasExportSheets, exportFilename } from "@/lib/nia-canvas-export";
import { hydrateCanvasFromThreadMessages } from "@/lib/nia-thread-utils";
import { canUseNia } from "@/lib/permissions";
import { downloadXlsx } from "@/lib/xlsx";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const HYDRATE_THREAD_CAP = 10;
const EMPTY_COPY =
  "Ask Nia to chart overdue invoices, sales by SKU, or dining vs sofas.";

// A local clear no longer skips this fetch: hydrate compares timestamps, so a
// chart persisted after that clear (e.g. a chart + SKU form in one turn) shows.
async function hydrateCanvasSpecFromThreads(): Promise<void> {
  if (readCanvasSpec()) {
    return;
  }
  const threads = await listNiaThreads();
  const candidates = threads.slice(0, HYDRATE_THREAD_CAP);
  const detailed = await Promise.all(candidates.map((summary) => getNiaThread(summary.id)));
  hydrateCanvasFromThreadMessages(detailed);
}

export default function CanvasPage() {
  const { user } = useAuth();
  const spec = useCanvasSpec();
  const empty = isEmptyCanvasSpec(spec);
  const exportSheets = spec ? canvasExportSheets(spec) : [];
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !canUseNia(user)) {
      return;
    }
    bindCanvasUser(user.id);
    if (readCanvasSpec()) {
      return;
    }
    void hydrateCanvasSpecFromThreads().catch(() => undefined);
  }, [user]);

  if (!user || !canUseNia(user)) {
    return (
      <section className="firstout-forbidden">
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
    <Stack gap={6} className="firstout-page">
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Canvas</h1>
          <p className="firstout-muted-text cds--type-body-01">
            {empty ? EMPTY_COPY : spec?.title}
          </p>
        </div>
        <div className="firstout-catalogue-actions">
          {exportSheets.length > 0 && spec ? (
            <Button
              kind="secondary"
              size="sm"
              renderIcon={DocumentExport}
              onClick={() => {
                setExportError(null);
                try {
                  downloadXlsx(
                    exportFilename(spec.title, todayIso()),
                    exportSheets,
                  );
                } catch (error) {
                  const message =
                    error instanceof Error ? error.message : "Export failed.";
                  setExportError(message);
                }
              }}
            >
              Export to Excel
            </Button>
          ) : null}
          <Button kind="ghost" size="sm" onClick={() => clearCanvasSpec()}>
            Clear canvas
          </Button>
        </div>
      </div>
      {exportError ? (
        <InlineNotification
          kind="error"
          title="Export failed"
          subtitle={exportError}
          onCloseButtonClick={() => setExportError(null)}
        />
      ) : null}
      {empty || !spec ? null : <CanvasSurface spec={spec} />}
    </Stack>
  );
}
