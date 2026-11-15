import { useState } from "react";
import { Button, Heading, FormControl, Select, Flash } from "@f0rge/primer";
import { ApiFailure } from "@f0rge/primer/api";
import { api, type StateResponse } from "./api/client";
import {
  currentOriginExports,
  downloadJson,
  mergeLegacy,
  object,
  type Kind,
  type ConflictPolicy,
  stable,
} from "./state";
import type { components } from "./api/generated";
import type { IdentitySession } from "./api/session";

export function ImportView({
  stored,
  kind,
  saved,
  session,
  onDenied,
}: {
  stored: StateResponse;
  kind: Kind;
  saved: (value: StateResponse) => void;
  session: IdentitySession;
  onDenied: (failure: ApiFailure) => void;
}) {
  const [source, setSource] = useState<unknown>(null);
  const [documents, setDocuments] = useState<
    { kind: Kind; document: unknown }[]
  >([]);
  const [policy, setPolicy] = useState<ConflictPolicy>("reject");
  const [legacyKind, setLegacyKind] = useState<Kind>(kind);
  const [error, setError] = useState("");
  const [serverPreview, setServerPreview] = useState<
    components["schemas"]["ImportPreview"] | null
  >(null);
  const [validatedBody, setValidatedBody] = useState<
    components["schemas"]["ImportWrite"] | null
  >(null);
  const [pending, setPending] = useState(false);
  const preview = mergeLegacy(stored.state, documents, policy);
  const body = {
    expected_revision: stored.revision,
    state: preview.state,
    source,
  };
  const previewCurrent =
    validatedBody !== null && stable(body) === stable(validatedBody);
  const read = async (file: File | undefined) => {
    if (!file) return;
    setServerPreview(null);
    setError("");
    try {
      if (file.size > 5 * 1024 * 1024)
        throw new Error(
          "This file exceeds the 5 MiB import limit. Retain it for assisted migration.",
        );
      const document: unknown = JSON.parse(await file.text());
      let docs: { kind: Kind; document: unknown }[];
      if (object(document) && Array.isArray(document.documents)) {
        docs = document.documents.map((entry) => {
          if (
            !object(entry) ||
            (entry.kind !== "bikes" && entry.kind !== "wheels") ||
            !("document" in entry)
          )
            throw new Error("Invalid multi-category export. No data changed.");
          return { kind: entry.kind, document: entry.document };
        });
      } else if (
        object(document) &&
        object(document.bikes) &&
        object(document.wheels)
      ) {
        docs = [
          { kind: "bikes", document: document.bikes },
          { kind: "wheels", document: document.wheels },
        ];
      } else docs = [{ kind: legacyKind, document }];
      setSource(document);
      setDocuments(docs);
    } catch (failure) {
      setDocuments([]);
      setSource(null);
      setError(
        failure instanceof Error
          ? failure.message
          : "The file could not be read.",
      );
    }
  };
  const review = async () => {
    setPending(true);
    setError("");
    try {
      const snapshot = structuredClone(body);
      const approved = await api.preview(snapshot, session);
      setValidatedBody(snapshot);
      setServerPreview(approved);
    } catch (failure) {
      if (!session.active) return;
      if (failure instanceof ApiFailure && failure.denied) {
        onDenied(failure);
        return;
      }
      setError(
        failure instanceof Error
          ? failure.message
          : "The server could not validate this import.",
      );
    } finally {
      setPending(false);
    }
  };
  const commit = async () => {
    if (!previewCurrent || !validatedBody) return;
    setPending(true);
    setError("");
    try {
      const result = await api.import(validatedBody, session);
      saved(result);
      setDocuments([]);
      setSource(null);
      setServerPreview(null);
    } catch (failure) {
      if (!session.active) return;
      if (failure instanceof ApiFailure && failure.denied) {
        onDenied(failure);
        return;
      }
      setError(
        failure instanceof ApiFailure && failure.conflict
          ? "Saved data changed after preview. Keep the original file, reload saved data and review again."
          : failure instanceof Error
            ? failure.message
            : "Import failed. No silent overwrite was attempted.",
      );
    } finally {
      setPending(false);
    }
  };
  return (
    <section className="panel stack">
      <Heading as="h2">Bring saved data</Heading>
      <p>
        Before a host or port change, export watches, trades and costs from{" "}
        <strong>every browser profile, device and old origin</strong> used for
        bikes and wheelsets. This page can read only this origin; it cannot
        retrieve another origin’s browser storage.
      </p>
      <div className="row">
        <Button
          onClick={() => {
            try {
              downloadJson(
                currentOriginExports(localStorage),
                "buycycle-browser-original.json",
              );
            } catch {
              setError(
                "Browser data could not be parsed. No storage was changed; preserve the original browser profile for manual recovery.",
              );
            }
          }}
        >
          Export original data from this browser
        </Button>
        <Button
          onClick={() =>
            downloadJson(stored.state, "buycycle-server-before-import.json")
          }
        >
          Export current server backup
        </Button>
      </div>
      <p className="muted">
        Exports read data without modifying or deleting the old localStorage
        keys. Keep the original files until reconciliation and the restoration
        rehearsal succeed.
      </p>
      <FormControl>
        <FormControl.Label>
          Category for an old single-category export
        </FormControl.Label>
        <Select
          value={legacyKind}
          onChange={(event) => {
            setLegacyKind(event.target.value === "wheels" ? "wheels" : "bikes");
            setDocuments([]);
            setSource(null);
            setServerPreview(null);
          }}
        >
          <Select.Option value="bikes">Bikes</Select.Option>
          <Select.Option value="wheels">Wheelsets</Select.Option>
        </Select>
      </FormControl>
      <label className="field">
        Choose an exported JSON file
        <input
          className="file"
          type="file"
          accept="application/json,.json"
          onChange={(event) => {
            void read(event.target.files?.[0]);
          }}
        />
      </label>
      {!!documents.length && (
        <>
          <Heading as="h3">Local preview — no writes yet</Heading>
          <p>
            {documents.length} category document(s) · {preview.counts.watches}{" "}
            watch entries · {preview.counts.trades} new trades ·{" "}
            {preview.counts.costs} cost values
          </p>
          {preview.errors.length > 0 && (
            <Flash variant="danger">
              <ul>
                {preview.errors.map((issue, index) => (
                  <li key={index}>{issue}</li>
                ))}
              </ul>
              <p>
                Nothing has been imported. The original file remains unchanged.
              </p>
            </Flash>
          )}
          {preview.conflicts.length > 0 && (
            <Flash variant="warning">
              <p>Conflicts require an explicit choice:</p>
              <ul>
                {preview.conflicts.map((issue, index) => (
                  <li key={index}>{issue}</li>
                ))}
              </ul>
            </Flash>
          )}
          <FormControl>
            <FormControl.Label>
              When imported values conflict with saved values
            </FormControl.Label>
            <Select
              value={policy}
              onChange={(event) => {
                setPolicy(event.target.value as ConflictPolicy);
                setServerPreview(null);
              }}
            >
              <Select.Option value="reject">Stop for review</Select.Option>
              <Select.Option value="keep_existing">
                Keep existing saved values
              </Select.Option>
              <Select.Option value="replace">Use imported values</Select.Option>
            </Select>
          </FormControl>
          <Button
            disabled={
              pending ||
              !!preview.errors.length ||
              (!!preview.conflicts.length && policy === "reject")
            }
            onClick={() => {
              void review();
            }}
          >
            Validate preview with server
          </Button>
          {serverPreview && (
            <Flash variant="success">
              <p>
                Server validation passed against revision{" "}
                {serverPreview.expected_revision}. Review the chosen conflict
                policy before committing.
              </p>
              <p>
                {serverPreview.counts.watches} watches ·{" "}
                {serverPreview.counts.trades} trades ·{" "}
                {serverPreview.counts.costs} cost values in the resulting state.
              </p>
              {serverPreview.warnings.map((warning, index) => (
                <p key={index}>{warning}</p>
              ))}
              {!previewCurrent && (
                <p role="status">
                  Saved data or import choices changed after validation.
                  Validate the preview again before confirming.
                </p>
              )}
              <Button
                variant="primary"
                disabled={pending || !previewCurrent}
                onClick={() => {
                  void commit();
                }}
              >
                Confirm import and retain original source
              </Button>
            </Flash>
          )}
        </>
      )}
      {error && (
        <Flash variant="danger">
          <p role="alert">{error}</p>
        </Flash>
      )}
      {pending && <span role="status">Checking saved data…</span>}
    </section>
  );
}
