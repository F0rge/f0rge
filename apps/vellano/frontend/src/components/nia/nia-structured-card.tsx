"use client";

import { Button, StructuredListBody, StructuredListRow, StructuredListWrapper, Tile } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import {
  resumeNiaThread,
  ApiError,
  type NiaMessage,
  type NiaNeedsOkPayload,
  type NiaOverdueInvoicesPayload,
  type NiaResumeDecision,
  type NiaStructuredPayload,
} from "@/lib/api";

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

function OpenedPageCard({ path, messageId }: { path: string; messageId: string }) {
  const router = useRouter();
  const navigatedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (navigatedRef.current.has(messageId)) {
      return;
    }
    navigatedRef.current.add(messageId);
    router.push(path);
  }, [messageId, path, router]);

  return (
    <Tile className="vellano-nia-card vellano-nia-card--nav">
      <p className="cds--type-label-01">Opened page</p>
      <p className="cds--type-body-01">{path}</p>
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
    return <OpenedPageCard path={structured.path} messageId={message.id} />;
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
