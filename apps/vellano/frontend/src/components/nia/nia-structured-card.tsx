"use client";

import {
  Button,
  Dropdown,
  NumberInput,
  StructuredListBody,
  StructuredListRow,
  StructuredListWrapper,
  TextArea,
  TextInput,
  Tile,
} from "@carbon/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  resumeNiaThread,
  ApiError,
  cancelTransfer,
  getTransfer,
  isCanvasClearedPayload,
  isCanvasSpecPayload,
  TRANSFER_STATUS_LABELS,
  type NiaFieldSpec,
  type NiaMessage,
  type NiaNeedsFieldsPayload,
  type NiaNeedsOkPayload,
  type NiaOverdueInvoicesPayload,
  type NiaResumeDecision,
  type NiaStructuredPayload,
  type NiaTransferDraftPayload,
  type TransferStatus,
} from "@/lib/api";
import { showViewCanvasButton } from "@/lib/nia-canvas-nav";
import { clearCanvasSpec, writeCanvasSpec } from "@/lib/nia-canvas-store";
import { niaInvoiceHref } from "@/lib/nia-navigation";
import { NiaCitationChips } from "./nia-citation-chips";

type NiaStructuredCardProps = {
  message: NiaMessage;
  threadId: string;
  onResumeComplete: () => void;
  onResumeError: (message: string) => void;
  streaming: boolean;
  actionable: boolean;
};

function isNeedsOk(payload: NiaStructuredPayload): payload is NiaNeedsOkPayload {
  return payload.kind === "needs_ok";
}

function isNeedsFields(payload: NiaStructuredPayload): payload is NiaNeedsFieldsPayload {
  return payload.kind === "needs_fields";
}

const FIELD_VALUE_ALIASES: Record<string, string[]> = {
  our_barcode: ["barcode", "our_barcode"],
  our_ref: ["sku", "sku_code", "ref", "our_ref"],
};

function lookupSuppliedValue(
  values: Record<string, unknown> | undefined,
  fieldId: string,
): unknown {
  if (!values) {
    return undefined;
  }
  if (values[fieldId] !== undefined && values[fieldId] !== null && String(values[fieldId]).trim() !== "") {
    return values[fieldId];
  }
  for (const alias of FIELD_VALUE_ALIASES[fieldId] ?? []) {
    const candidate = values[alias];
    if (candidate !== undefined && candidate !== null && String(candidate).trim() !== "") {
      return candidate;
    }
  }
  return undefined;
}

export function initialFieldValues(payload: NiaNeedsFieldsPayload): Record<string, string> {
  const values: Record<string, string> = {};
  for (const field of payload.fields) {
    const fieldValue: unknown = field.value;
    if (fieldValue !== undefined && fieldValue !== null) {
      const coerced = String(fieldValue);
      if (coerced.trim() !== "") {
        values[field.id] = coerced;
        continue;
      }
    }
    const supplied = lookupSuppliedValue(payload.values, field.id);
    if (supplied !== undefined && supplied !== null) {
      values[field.id] = String(supplied);
      continue;
    }
    values[field.id] = "";
  }
  return values;
}

export function coerceNeedsFieldsValues(
  fields: NiaFieldSpec[],
  raw: Record<string, string>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of fields) {
    const value = (raw[field.id] ?? "").trim();
    if (!value) {
      continue;
    }
    if (field.type === "number") {
      const parsed = Number(value);
      out[field.id] = Number.isFinite(parsed) ? parsed : value;
      continue;
    }
    if (field.type === "boolean") {
      out[field.id] = value === "true";
      continue;
    }
    if (field.type === "json") {
      try {
        out[field.id] = JSON.parse(value);
      } catch {
        out[field.id] = value;
      }
      continue;
    }
    out[field.id] = value;
  }
  return out;
}

export function fieldHasValue(value: string | undefined): boolean {
  return (value ?? "").trim() !== "";
}

export function isMissingRequiredError(error: string | undefined): boolean {
  if (!error) return false;
  const normalized = error.trim().toLowerCase();
  return (
    normalized === "field required" ||
    normalized === "required" ||
    normalized.includes("field required") ||
    normalized.includes("field should not be empty")
  );
}

export function isNeedsFieldInvalid(
  field: Pick<NiaFieldSpec, "required" | "error">,
  currentValue: string | undefined,
): boolean {
  if (fieldHasValue(currentValue)) {
    if (!field.error) return false;
    if (isMissingRequiredError(field.error)) return false;
    return true; // keep real format/type errors
  }
  if (field.required) return true;
  return Boolean(field.error);
}

export function needsFieldsFormComplete(
  fields: Array<Pick<NiaFieldSpec, "id" | "required">>,
  values: Record<string, string>,
): boolean {
  return fields.every((field) => !field.required || fieldHasValue(values[field.id]));
}

function NeedsFieldsCard({
  payload,
  threadId,
  streaming,
  onResumeComplete,
  onResumeError,
}: {
  payload: NiaNeedsFieldsPayload;
  threadId: string;
  streaming: boolean;
  onResumeComplete: () => void;
  onResumeError: (message: string) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => initialFieldValues(payload));
  const [submitting, setSubmitting] = useState(false);

  function setField(id: string, value: string) {
    setValues((current) => ({ ...current, [id]: value }));
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await resumeNiaThread(
        threadId,
        "submit_fields",
        undefined,
        undefined,
        coerceNeedsFieldsValues(payload.fields, values),
      );
      onResumeComplete();
    } catch (err: unknown) {
      onResumeError(err instanceof ApiError ? err.message : "Failed to submit fields");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Tile className="vellano-nia-card vellano-nia-card--fields">
      <p className="cds--type-label-01">{payload.title}</p>
      {payload.body ? <p className="cds--type-body-01">{payload.body}</p> : null}
      <div className="vellano-nia-card__fields">
        {payload.fields.map((field) => {
          const invalid = isNeedsFieldInvalid(field, values[field.id]);
          const invalidText = !invalid
            ? undefined
            : field.error && !isMissingRequiredError(field.error)
              ? field.error
              : "Field required";
          if (field.type === "number") {
            return (
              <NumberInput
                key={field.id}
                id={`nia-field-${field.id}`}
                label={field.label}
                value={values[field.id] ?? ""}
                required={field.required}
                invalid={invalid}
                invalidText={invalidText}
                hideSteppers
                onChange={(_event, state) => {
                  const next = state?.value;
                  setField(field.id, next === undefined || next === "" ? "" : String(next));
                }}
              />
            );
          }
          if (field.type === "select" || field.type === "boolean") {
            const items = field.options ?? [];
            const selected = items.find((item) => item.id === values[field.id]) ?? null;
            return (
              <Dropdown
                key={field.id}
                id={`nia-field-${field.id}`}
                titleText={field.label}
                label="Choose"
                items={items}
                itemToString={(item) => (item ? item.text : "")}
                selectedItem={selected}
                invalid={invalid}
                invalidText={invalidText}
                onChange={({ selectedItem }) => {
                  setField(field.id, selectedItem?.id ?? "");
                }}
              />
            );
          }
          if (field.type === "json") {
            return (
              <TextArea
                key={field.id}
                id={`nia-field-${field.id}`}
                labelText={field.label}
                value={values[field.id] ?? ""}
                required={field.required}
                invalid={invalid}
                invalidText={invalidText}
                rows={4}
                onChange={(event) => setField(field.id, event.target.value)}
              />
            );
          }
          return (
            <TextInput
              key={field.id}
              id={`nia-field-${field.id}`}
              labelText={field.label}
              type={field.type === "date" ? "date" : "text"}
              value={values[field.id] ?? ""}
              required={field.required}
              invalid={invalid}
              invalidText={invalidText}
              onChange={(event) => setField(field.id, event.target.value)}
            />
          );
        })}
      </div>
      <div className="vellano-nia-card__actions">
        <Button
          size="sm"
          kind="primary"
          disabled={streaming || submitting || !needsFieldsFormComplete(payload.fields, values)}
          onClick={() => void handleSubmit()}
        >
          Continue
        </Button>
      </div>
    </Tile>
  );
}

function isOverdueInvoices(payload: NiaStructuredPayload): payload is NiaOverdueInvoicesPayload {
  return payload.kind === "overdue_invoices";
}

function isTransferDraft(payload: NiaStructuredPayload): payload is NiaTransferDraftPayload {
  return payload.kind === "transfer_draft";
}

function CanvasSpecCard({
  title,
  spec,
}: {
  title: string;
  spec: Parameters<typeof writeCanvasSpec>[0];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const showView = showViewCanvasButton(pathname);

  function handleView() {
    writeCanvasSpec(spec);
    router.push("/canvas");
  }

  return (
    <Tile className="vellano-nia-card vellano-nia-card--nav">
      <p className="cds--type-label-01">Canvas</p>
      <p className="cds--type-body-01">{title}</p>
      {showView ? (
        <div className="vellano-nia-card__actions">
          <Button size="sm" kind="primary" onClick={handleView}>
            View Canvas
          </Button>
        </div>
      ) : null}
    </Tile>
  );
}

function CanvasClearedCard() {
  const router = useRouter();
  const pathname = usePathname();

  function handleView() {
    clearCanvasSpec();
    router.push("/canvas");
  }

  return (
    <Tile className="vellano-nia-card vellano-nia-card--nav">
      <p className="cds--type-label-01">Canvas</p>
      <p className="cds--type-body-01">Canvas cleared</p>
      {showViewCanvasButton(pathname) ? (
        <div className="vellano-nia-card__actions">
          <Button size="sm" kind="ghost" onClick={handleView}>
            View Canvas
          </Button>
        </div>
      ) : null}
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
  actionable,
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

  // Successful `opened_page` payloads navigate in applyPostRunNavigation;
  // never render a second View/Open-page action for the same turn.
  if (structured.kind === "opened_page") {
    return null;
  }

  if (isCanvasSpecPayload(structured)) {
    return <CanvasSpecCard title={structured.title} spec={structured} />;
  }

  if (isCanvasClearedPayload(structured)) {
    return <CanvasClearedCard />;
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
                    <Link
                      className="cds--link cds--type-body-01"
                      href={niaInvoiceHref(invoice.id)}
                    >
                      {invoice.invoice_number}
                    </Link>
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

  if (isNeedsFields(structured)) {
    return (
      <NeedsFieldsCard
        payload={structured}
        threadId={threadId}
        streaming={streaming}
        onResumeComplete={onResumeComplete}
        onResumeError={onResumeError}
      />
    );
  }

  if (isNeedsOk(structured)) {
    return (
      <Tile className="vellano-nia-card vellano-nia-card--approval">
        <p className="cds--type-label-01">{structured.title}</p>
        <p className="cds--type-body-01">{structured.body}</p>
        {actionable ? (
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
        ) : null}
      </Tile>
    );
  }

  return null;
}
