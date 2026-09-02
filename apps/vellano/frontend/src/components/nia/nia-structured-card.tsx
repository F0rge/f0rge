"use client";

import { Button, StructuredListBody, StructuredListRow, StructuredListWrapper, Tile } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  resumeNiaThread,
  ApiError,
  cancelTransfer,
  getTransfer,
  isCanvasSpecPayload,
  TRANSFER_STATUS_LABELS,
  type NiaMessage,
  type NiaNeedsOkPayload,
  type NiaOverdueInvoicesPayload,
  type NiaResumeDecision,
  type NiaStructuredPayload,
  type NiaTransferDraftPayload,
  type TransferStatus,
} from "@/lib/api";
import { writeCanvasSpec } from "@/lib/nia-canvas-store";
import { labelForNavPath } from "@/lib/nav";

import { NiaCitationChips } from "./nia-citation-chips";

type NiaStructuredCardProps = {
  message: NiaMessage;
  threadId: string;
  onResumeComplete: () => void;
  onResumeError: (message: string) => void;
  streaming: boolean;
};

function isNeedsOk(payload: NiaStructuredPayload): payload is NiaNeedsOkPayload {
  return payload.kind === "needs_ok";
}

function isOverdueInvoices(payload: NiaStructuredPayload): payload is NiaOverdueInvoicesPayload {
  return payload.kind === "overdue_invoices";
}

function isTransferDraft(payload: NiaStructuredPayload): payload is NiaTransferDraftPayload {
  return payload.kind === "transfer_draft";
}

function OpenedPageCard({ path }: { path: string }) {
  const router = useRouter();
  const label = labelForNavPath(path);

  return (
    <Tile className="vellano-nia-card vellano-nia-card--nav">
      <p className="cds--type-label-01">Opened page</p>
      <p className="cds--type-body-01">{label}</p>
      <div className="vellano-nia-card__actions">
        <Button size="sm" kind="primary" onClick={() => router.push(path)}>
          Open {label}
        </Button>
      </div>
    </Tile>
  );
}

function CanvasSpecCard({
  title,
  spec,
}: {
  title: string;
  spec: Parameters<typeof writeCanvasSpec>[0];
}) {
  const router = useRouter();

  function handleView() {
    writeCanvasSpec(spec);
    router.push("/canvas");
  }

  return (
    <Tile className="vellano-nia-card vellano-nia-card--nav">
      <p className="cds--type-label-01">Canvas</p>
      <p className="cds--type-body-01">{title}</p>
      <div className="vellano-nia-card__actions">
        <Button size="sm" kind="primary" onClick={handleView}>
          View Canvas
        </Button>
      </div>
    </Tile>
  );
}

function TransferDraftCard({
  payload,
  onError,
}: {
  payload: NiaTransferDraftPayload;
  onError: (message: string) => void;
}) {
  const router = useRouter();
  const [liveStatus, setLiveStatus] = useState<TransferStatus>(payload.status);
  const [undoHidden, setUndoHidden] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [blockedMessage, setBlockedMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getTransfer(payload.transfer_id)
      .then((transfer) => {
        if (!cancelled) {
          setLiveStatus(transfer.status);
        }
      })
      .catch(() => {
        // Keep payload status when refresh fails.
      });
    return () => {
      cancelled = true;
    };
  }, [payload.transfer_id]);

  const showUndo = payload.undoable && liveStatus === "draft" && !undoHidden && !undoing;

  async function handleUndo() {
    setUndoing(true);
    try {
      const cancelled = await cancelTransfer(payload.transfer_id);
      setLiveStatus(cancelled.status);
      setUndoHidden(true);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        setUndoHidden(true);
        setBlockedMessage("Already dispatched — reverse in Transfers");
        try {
          const transfer = await getTransfer(payload.transfer_id);
          setLiveStatus(transfer.status);
        } catch {
          setLiveStatus("in_transit");
        }
      } else {
        onError(err instanceof ApiError ? err.message : "Failed to cancel transfer");
      }
    } finally {
      setUndoing(false);
    }
  }

  const statusLabel = TRANSFER_STATUS_LABELS[liveStatus] ?? liveStatus;
  const dispatchedNote =
    liveStatus === "in_transit"
      ? "Dispatched — stock left the source. Receive or reverse in Transfers."
      : null;

  return (
    <Tile className="vellano-nia-card vellano-nia-card--undo">
      <p className="cds--type-label-01">Transfer draft</p>
      <p className="cds--type-body-01">{payload.transfer_number}</p>
      <p className="vellano-muted-text">Status: {statusLabel}</p>
      {dispatchedNote ? <p className="cds--type-body-01">{dispatchedNote}</p> : null}
      {blockedMessage ? <p className="cds--type-body-01">{blockedMessage}</p> : null}
      <NiaCitationChips citations={payload.citations} />
      {showUndo ? (
        <div className="vellano-nia-card__actions">
          <Button size="sm" kind="danger--tertiary" disabled={undoing} onClick={() => void handleUndo()}>
            Undo
          </Button>
          <Button size="sm" kind="ghost" onClick={() => router.push("/transfers")}>
            Open Transfers
          </Button>
        </div>
      ) : null}
    </Tile>
  );
}

export function NiaStructuredCard({
  message,
  threadId,
  onResumeComplete,
  onResumeError,
  streaming,
}: NiaStructuredCardProps) {
  const payload = message.structured_payload;
  if (!payload || typeof payload !== "object" || !("kind" in payload)) {
    return null;
  }

  const structured = payload;

  async function handleDecision(decision: NiaResumeDecision) {
    if (!isNeedsOk(structured)) {
      return;
    }
    try {
      await resumeNiaThread(threadId, decision, structured.tool_call_id);
      onResumeComplete();
    } catch (err: unknown) {
      onResumeError(err instanceof ApiError ? err.message : "Failed to resume Nia");
    }
  }

  if (structured.kind === "opened_page" && typeof structured.path === "string") {
    return <OpenedPageCard path={structured.path} />;
  }

  if (isCanvasSpecPayload(structured)) {
    return <CanvasSpecCard title={structured.title} spec={structured} />;
  }

  if (isTransferDraft(structured)) {
    return <TransferDraftCard payload={structured} onError={onResumeError} />;
  }

  if (isOverdueInvoices(structured)) {
    return (
      <Tile className="vellano-nia-card vellano-nia-card--list">
        <p className="cds--type-label-01">Overdue invoices</p>
        {structured.invoices.length === 0 ? (
          <p className="cds--type-body-01">No overdue invoices.</p>
        ) : (
          <StructuredListWrapper>
            <StructuredListBody>
              {structured.invoices.map((invoice) => (
                <StructuredListRow key={invoice.id}>
                  <div>
                    <p className="cds--type-body-01">{invoice.invoice_number}</p>
                    <p className="vellano-muted-text">R {invoice.remaining_zar} remaining</p>
                  </div>
                </StructuredListRow>
              ))}
            </StructuredListBody>
          </StructuredListWrapper>
        )}
        <NiaCitationChips citations={structured.citations} />
      </Tile>
    );
  }

  if (structured.kind === "your_call") {
    const title =
      typeof structured.title === "string" ? structured.title : "Choose an option";
    const body = typeof structured.body === "string" ? structured.body : "";
    return (
      <Tile className="vellano-nia-card vellano-nia-card--choice">
        <p className="cds--type-label-01">{title}</p>
        {body ? <p className="cds--type-body-01">{body}</p> : null}
      </Tile>
    );
  }

  if (isNeedsOk(structured)) {
    return (
      <Tile className="vellano-nia-card vellano-nia-card--approval">
        <p className="cds--type-label-01">{structured.title}</p>
        <p className="cds--type-body-01">{structured.body}</p>
        <div className="vellano-nia-card__actions">
          <Button
            size="sm"
            kind="primary"
            disabled={streaming}
            onClick={() => void handleDecision("accept")}
          >
            Accept
          </Button>
          <Button
            size="sm"
            kind="secondary"
            disabled={streaming}
            onClick={() => void handleDecision("decline")}
          >
            Decline
          </Button>
          <Button
            size="sm"
            kind="ghost"
            disabled={streaming}
            onClick={() => void handleDecision("cancel")}
          >
            Cancel
          </Button>
        </div>
      </Tile>
    );
  }

  return null;
}
