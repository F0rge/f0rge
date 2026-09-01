"use client";

import { Button, InlineNotification, Stack, TextInput } from "@carbon/react";
import { Checkmark } from "@carbon/icons-react";
import { useRef, useState } from "react";

import {
  ApiError,
  cancelStocktake,
  completeStocktake,
  lookupStocktakeBarcode,
  patchStocktakeLine,
  type Stocktake,
  type StocktakeLine,
} from "@/lib/api";

import { StocktakeLinesTable, type DraftQty } from "./stocktake-lines-table";

type StocktakeSessionProps = {
  stocktake: Stocktake;
  canMutate: boolean;
  onLinePatched: (line: StocktakeLine) => void;
  onFinished: () => Promise<void>;
  onError: (message: string) => void;
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-ZA");
}

function draftsFromLines(lines: StocktakeLine[]): Record<string, DraftQty> {
  const next: Record<string, DraftQty> = {};
  for (const line of lines) {
    next[line.id] = line.counted_qty ?? "";
  }
  return next;
}

export function StocktakeSession({
  stocktake,
  canMutate,
  onLinePatched,
  onFinished,
  onError,
}: StocktakeSessionProps) {
  const [barcode, setBarcode] = useState("");
  const [drafts, setDrafts] = useState<Record<string, DraftQty>>(() =>
    draftsFromLines(stocktake.lines),
  );
  const draftsRef = useRef(drafts);
  const [highlightedLineId, setHighlightedLineId] = useState<string | null>(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [busy, setBusy] = useState(false);

  function setDraftValue(lineId: string, value: DraftQty) {
    setDrafts((current) => {
      const next = { ...current, [lineId]: value };
      draftsRef.current = next;
      return next;
    });
  }

  function focusCounted(lineId: string) {
    setHighlightedLineId(lineId);
    const input = document.getElementById(`stocktake-counted-${lineId}`);
    if (input instanceof HTMLInputElement) {
      input.focus();
      input.select();
      input.closest("tr")?.scrollIntoView({ block: "center" });
    }
  }

  async function saveLine(lineId: string) {
    if (!canMutate) {
      return;
    }
    const line = stocktake.lines.find((entry) => entry.id === lineId);
    const draft = draftsRef.current[lineId];
    if (!line || draft === "" || draft === line.counted_qty) {
      return;
    }
    try {
      const updated = await patchStocktakeLine(stocktake.id, lineId, { counted_qty: draft });
      onLinePatched(updated);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to save counted quantity.");
    }
  }

  async function flushDrafts() {
    const pending = stocktake.lines.filter((line) => {
      const draft = draftsRef.current[line.id];
      return draft !== "" && draft !== line.counted_qty;
    });
    await Promise.all(
      pending.map((line) =>
        patchStocktakeLine(stocktake.id, line.id, {
          counted_qty: draftsRef.current[line.id] as number,
        }),
      ),
    );
  }

  async function handleLookup() {
    const trimmed = barcode.trim();
    if (!canMutate || !trimmed) {
      return;
    }
    setLookingUp(true);
    try {
      const line = await lookupStocktakeBarcode(stocktake.id, { barcode: trimmed });
      setBarcode("");
      focusCounted(line.id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        onError(err.message || "No line matches that barcode.");
      } else {
        onError(err instanceof Error ? err.message : "Barcode lookup failed.");
      }
    } finally {
      setLookingUp(false);
    }
  }

  async function handleComplete() {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
      await flushDrafts();
      await completeStocktake(stocktake.id);
      await onFinished();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to complete stocktake.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
      await cancelStocktake(stocktake.id);
      await onFinished();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to cancel stocktake.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack gap={6}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1 className="cds--type-productive-heading-04">{stocktake.location_name} stocktake</h1>
          <p className="cds--type-body-01">
            Started {formatDateTime(stocktake.started_at)} • In progress
          </p>
        </div>
        {canMutate ? (
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <Button kind="danger" disabled={busy} onClick={() => void handleCancel()}>
              Cancel stocktake
            </Button>
            <Button disabled={busy} renderIcon={Checkmark} onClick={() => void handleComplete()}>
              Complete & Adjust
            </Button>
          </div>
        ) : null}
      </div>

      <InlineNotification
        kind="warning"
        title="Location locked"
        subtitle={`${stocktake.location_name} is locked for inventory movements until this stocktake is completed or cancelled.`}
        hideCloseButton
        lowContrast
      />

      {canMutate ? (
        <div
          style={{
            display: "flex",
            gap: "1rem",
            alignItems: "flex-end",
            maxWidth: "32rem",
          }}
        >
          <div style={{ flex: 1 }}>
            <TextInput
              id="stocktake-barcode"
              labelText="Search / barcode"
              placeholder="Scan or type our barcode"
              value={barcode}
              onChange={(event) => setBarcode(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleLookup();
                }
              }}
            />
          </div>
          <Button disabled={lookingUp || !barcode.trim()} onClick={() => void handleLookup()}>
            Lookup
          </Button>
        </div>
      ) : null}

      {stocktake.lines.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="This location has no catalogue lines to count."
          hideCloseButton
          lowContrast
        />
      ) : (
        <StocktakeLinesTable
          lines={stocktake.lines}
          drafts={drafts}
          highlightedLineId={highlightedLineId}
          canMutate={canMutate}
          busy={busy}
          onDraftChange={setDraftValue}
          onCountedBlur={(lineId) => void saveLine(lineId)}
        />
      )}
    </Stack>
  );
}
