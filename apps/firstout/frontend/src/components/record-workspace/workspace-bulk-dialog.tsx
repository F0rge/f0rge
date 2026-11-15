"use client";

import {
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  TextInput,
} from "@carbon/react";
import { useState } from "react";
import { bulkPatch, type BulkFieldChange } from "@/lib/record-workspace";
import {
  executeWorkspace,
  preflightWorkspace,
  type WorkspaceAction,
  type WorkspaceExecution,
  type WorkspacePreflight,
  type WorkspaceResource,
  type WorkspaceSelection,
} from "@/lib/record-workspace-api";
import { WorkspaceFieldValue } from "./workspace-filters";
import type { WorkspaceField } from "./types";
import styles from "./record-workspace.module.css";

export interface WorkspaceOperation {
  action: WorkspaceAction;
  label: string;
  selection: WorkspaceSelection;
  count: number;
}
export function WorkspaceBulkDialog({
  resource,
  operation,
  fields,
  onClose,
  onComplete,
}: {
  resource: WorkspaceResource;
  operation: WorkspaceOperation;
  fields: readonly WorkspaceField[];
  onClose: () => void;
  onComplete: (message: string) => void;
}) {
  const [changes, setChanges] = useState<Record<string, BulkFieldChange>>({});
  const [preview, setPreview] = useState<WorkspacePreflight | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [result, setResult] = useState<WorkspaceExecution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const editing = operation.action === "edit";
  const destructive = operation.action === "delete";
  const change = (field: string, patch: Partial<BulkFieldChange>) => {
    setChanges((current) => ({
      ...current,
      [field]: { ...(current[field] ?? { mode: "keep", value: "" }), ...patch },
    }));
    setPreview(null);
    setRequestId(null);
    setError(null);
  };
  async function submit() {
    if (result) {
      onClose();
      return;
    }
    setError(null);
    setBusy(true);
    try {
      if (!preview) {
        const patch = editing ? bulkPatch(fields, changes) : undefined;
        const next = await preflightWorkspace(resource, {
          ...operation.selection,
          action: operation.action,
          ...(patch ? { patch } : {}),
        });
        setPreview(next);
        setRequestId(crypto.randomUUID());
      } else if (requestId) {
        const next = await executeWorkspace(
          resource,
          preview.preflight_token,
          requestId,
        );
        setResult(next);
        onComplete(
          `${next.succeeded.length} record${next.succeeded.length === 1 ? "" : "s"} updated${next.failed.length ? `; ${next.failed.length} could not be changed` : ""}.`,
        );
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not complete this operation.",
      );
    } finally {
      setBusy(false);
    }
  }
  const primary = result
    ? "Done"
    : busy
      ? "Working…"
      : preview
        ? `${operation.label} ${preview.eligible_count} eligible`
        : "Preview changes";
  return (
    <Modal
      open
      modalHeading={`${operation.label} ${operation.count} record${operation.count === 1 ? "" : "s"}`}
      modalLabel="Review changes"
      primaryButtonText={primary}
      secondaryButtonText={result ? undefined : "Cancel"}
      danger={destructive && !result}
      primaryButtonDisabled={
        busy ||
        (!!preview &&
          !result &&
          (preview.eligible_count === 0 ||
            (destructive && confirmation !== "DELETE")))
      }
      onRequestClose={() => {
        if (!busy) onClose();
      }}
      onRequestSubmit={() => void submit()}
      size="md"
      className={styles.modal}
    >
      <div className={styles.dialogBody}>
        {error && (
          <InlineNotification
            kind="error"
            title="Could not complete changes"
            subtitle={error}
            hideCloseButton
            lowContrast
          />
        )}
        {!result && editing && (
          <>
            <p>
              Only selected fields will change. Existing documents keep their
              recorded values.
            </p>
            {fields.map((field) => {
              const current = changes[field.key] ?? { mode: "keep", value: "" };
              return (
                <div className={styles.bulkField} key={field.key}>
                  <strong>{field.label}</strong>
                  <Select
                    id={`bulk-${field.key}-mode`}
                    labelText={`${field.label}: change`}
                    disabled={busy}
                    value={current.mode}
                    onChange={(event) =>
                      change(field.key, {
                        mode: event.target.value as BulkFieldChange["mode"],
                      })
                    }
                  >
                    <SelectItem value="keep" text="Leave unchanged" />
                    <SelectItem value="set" text="Set value" />
                    {field.nullable && (
                      <SelectItem value="clear" text="Clear value" />
                    )}
                  </Select>
                  <div>
                    <label
                      className="cds--label"
                      htmlFor={`bulk-${field.key}-value`}
                    >
                      New value
                    </label>
                    <WorkspaceFieldValue
                      id={`bulk-${field.key}-value`}
                      field={field}
                      value={current.value}
                      onChange={(value) =>
                        change(field.key, { value: String(value ?? "") })
                      }
                      disabled={busy || current.mode !== "set"}
                    />
                  </div>
                </div>
              );
            })}
          </>
        )}
        {!result && !editing && (
          <p>
            {destructive
              ? "Permanent deletion is limited to records the server confirms are eligible. This cannot be undone."
              : "Records retain their details and history. Review eligibility before applying this operation."}
          </p>
        )}
        {preview && !result && (
          <>
            <div className={styles.preflightSummary}>
              <strong>
                {preview.eligible_count} eligible · {preview.blocked_count}{" "}
                blocked
              </strong>
              <span>Only the eligible records listed below will change.</span>
            </div>
            {editing && (
              <dl className={styles.details}>
                {Object.entries(bulkPatch(fields, changes)).map(
                  ([key, value]) => (
                    <div key={key}>
                      <dt>
                        {fields.find((field) => field.key === key)?.label ??
                          key}
                      </dt>
                      <dd>{value === null ? "Clear value" : String(value)}</dd>
                    </div>
                  ),
                )}
              </dl>
            )}
            <ul className={styles.preflightList}>
              {preview.eligible.map((item) => (
                <li key={item.id}>
                  <span>{item.label}</span>
                  <span>Eligible</span>
                </li>
              ))}
              {preview.blocked.map((item) => (
                <li key={item.id}>
                  <span>{item.label}</span>
                  <span>{item.reason}</span>
                </li>
              ))}
            </ul>
            {destructive && (
              <TextInput
                id="workspace-delete-confirm"
                labelText="Type DELETE to confirm"
                disabled={busy}
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
                autoComplete="off"
              />
            )}
          </>
        )}
        {result && (
          <>
            <InlineNotification
              kind={result.failed.length ? "warning" : "success"}
              title={`${result.succeeded.length} records changed`}
              subtitle={
                result.replayed
                  ? "The previously completed result was recovered safely."
                  : "The table has been refreshed."
              }
              hideCloseButton
              lowContrast
            />
            {result.failed.length > 0 && (
              <ul className={styles.preflightList}>
                {result.failed.map((item) => (
                  <li key={item.id}>
                    <span>{item.id}</span>
                    <span>{item.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}
