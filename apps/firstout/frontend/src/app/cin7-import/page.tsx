// Superdesign CLI is not installed in this environment. The page uses Carbon.
"use client";

import {
  Button,
  DataTable,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  commitCin7Import,
  downloadCin7Barcodes,
  downloadCin7Errors,
  downloadCin7Warnings,
  getCin7Import,
  listCin7Imports,
  startCin7Import,
  type Cin7ImportRun,
} from "@/lib/api";
import {
  appendCin7Files,
  canSeeCin7Import,
  commitBlockedReason,
  fileSelectionKey,
  generatedBarcodeHeadline,
  importHeadlines,
  isActiveRun,
} from "@/lib/cin7-import";
import { useAuth } from "@/lib/auth";

const ENTITY_HEADERS = [
  { key: "entity", header: "Entity" },
  { key: "created", header: "Created" },
  { key: "updated", header: "Updated" },
  { key: "unchanged", header: "Unchanged" },
  { key: "skipped", header: "Skipped" },
] as const;

const HISTORY_HEADERS = [
  { key: "when", header: "When" },
  { key: "who", header: "Who" },
  { key: "file", header: "File" },
  { key: "mode", header: "Mode" },
  { key: "status", header: "Status" },
  { key: "warnings", header: "Warnings" },
  { key: "errors", header: "Errors" },
] as const;

const PRICE_TIERS = ["stockist", "wholesale", "decorator", "retail"] as const;

function HeadlineStrip({ run }: { run: Cin7ImportRun }) {
  const headlines = importHeadlines(run.summary);
  const barcodeTitle = generatedBarcodeHeadline(
    headlines.generatedBarcodes,
    headlines.generatedBarcodesBlank,
    headlines.generatedBarcodesShared,
  );
  const figures = [
    ["SKUs updated", headlines.skusUpdated],
    ["Customers updated", headlines.customersUpdated],
    ["Price lists created", headlines.priceListsCreated],
    ["Price-list items created", headlines.priceListItemsCreated],
    ["Errors", run.error_count],
  ] as const;
  return (
    <Stack gap={4}>
      <Stack orientation="horizontal" gap={5}>
        {figures.map(([label, value]) => (
          <div key={label}>
            <p className="cds--type-helper-text-01">{label}</p>
            <p className="cds--type-productive-heading-03">{value.toLocaleString("en-GB")}</p>
          </div>
        ))}
      </Stack>
      <InlineNotification
        kind={headlines.generatedBarcodes > 0 ? "warning" : "info"}
        title={barcodeTitle}
        subtitle="A blank barcode, or one shared with another product, is replaced with CIN7-{product code}. The lowest product code keeps a shared barcode."
        hideCloseButton
      />
      <div>
        <Button kind="tertiary" onClick={() => void downloadCin7Barcodes(run.id)}>
          Download generated barcodes ({headlines.generatedBarcodes})
        </Button>
      </div>
    </Stack>
  );
}

function formatWhen(value: string | null): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function modeLabel(mode: Cin7ImportRun["mode"]): string {
  return mode === "commit" ? "Commit" : "Dry run";
}

export default function Cin7ImportPage() {
  const { user } = useAuth();
  const allowed = canSeeCin7Import(user?.permissions);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadedKey, setUploadedKey] = useState("");
  const [run, setRun] = useState<Cin7ImportRun | null>(null);
  const [history, setHistory] = useState<Cin7ImportRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const selectedKey = fileSelectionKey(files);
  const blocked = commitBlockedReason(run, selectedKey, uploadedKey);

  const loadHistory = useCallback(async () => {
    const rows = await listCin7Imports();
    setHistory(rows);
  }, []);

  useEffect(() => {
    if (!allowed) {
      return;
    }
    void loadHistory().catch((caught: unknown) => {
      setError(caught instanceof ApiError ? caught.message : "Could not load import history");
    });
  }, [allowed, loadHistory]);

  useEffect(() => {
    if (!run || !isActiveRun(run.status)) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getCin7Import(run.id)
        .then((next) => {
          if (!cancelled) {
            setRun(next);
            if (!isActiveRun(next.status)) {
              void loadHistory();
            }
          }
        })
        .catch((caught: unknown) => {
          if (!cancelled) {
            setError(caught instanceof ApiError ? caught.message : "Could not read import status");
          }
        });
    }, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [loadHistory, run]);

  if (!allowed) {
    return (
      <section className="firstout-forbidden">
        <InlineNotification
          kind="error"
          title="Forbidden"
          subtitle="Cin7 import is limited to the owner role."
          hideCloseButton
        />
      </section>
    );
  }

  async function dryRun() {
    setBusy(true);
    setError(null);
    setRun(null);
    const body = new FormData();
    appendCin7Files(body, files);
    try {
      const started = await startCin7Import(body);
      setUploadedKey(fileSelectionKey(files));
      setRun(started);
      await loadHistory();
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "Dry run failed");
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (!run) {
      return;
    }
    setConfirmOpen(false);
    setBusy(true);
    setError(null);
    try {
      const started = await commitCin7Import(run.id, run.file_sha256);
      setRun(started);
      await loadHistory();
    } catch (caught: unknown) {
      setError(caught instanceof ApiError ? caught.message : "Commit failed");
    } finally {
      setBusy(false);
    }
  }

  const entityRows = Object.entries(run?.summary.entities ?? {}).map(([name, counts]) => ({
    id: name,
    entity: name,
    created: String(counts.created),
    updated: String(counts.updated),
    unchanged: String(counts.unchanged),
    skipped: String(counts.skipped),
  }));

  const historyRows = history.map((entry) => ({
    id: entry.id,
    when: formatWhen(entry.finished_at ?? entry.created_at),
    who: entry.user_email,
    file: entry.file_name,
    mode: modeLabel(entry.mode),
    status: entry.status,
    warnings: String(entry.warning_count),
    errors: String(entry.error_count),
  }));

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Cin7 import</h1>
        <p className="cds--type-body-01">
          Upload the Cin7 export zip, or the files from its cin7-export folder. Dry run is the
          default and writes nothing. Commit is available only after a clean dry run of that same
          file.
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Import"
          subtitle={error}
          onClose={() => setError(null)}
        />
      ) : null}

      <FileUploaderDropContainer
        accept={[".zip", ".csv", ".xlsx"]}
        labelText="Drag and drop the Cin7 zip or export files, or click to upload"
        multiple
        disabled={busy}
        onAddFiles={(_event, { addedFiles }) => {
          const next = addedFiles.filter((file): file is File => file instanceof File);
          setFiles(next);
          setRun(null);
          setUploadedKey("");
        }}
      />
      {files.map((file) => (
        <FileUploaderItem key={`${file.name}-${file.size}`} name={file.name} status="edit" />
      ))}

      <Stack orientation="horizontal" gap={4}>
        <Button kind="secondary" disabled={busy || files.length === 0} onClick={() => void dryRun()}>
          {busy && !run ? "Starting…" : "Dry run"}
        </Button>
        <Button kind="danger" disabled={busy || blocked !== null} onClick={() => setConfirmOpen(true)}>
          Commit import
        </Button>
      </Stack>
      {blocked && run ? <p className="cds--type-helper-text-01">{blocked}</p> : null}

      {run && isActiveRun(run.status) ? (
        <InlineNotification
          kind="info"
          title={modeLabel(run.mode)}
          subtitle="Working. This page checks the job until it finishes."
          hideCloseButton
        />
      ) : null}

      {run && !isActiveRun(run.status) ? (
        <Stack gap={5}>
          <Stack orientation="horizontal" gap={3}>
            <Tag type={run.status === "completed" ? "green" : "red"}>{run.status}</Tag>
            <Tag type="cool-gray">{modeLabel(run.mode)}</Tag>
            <span className="cds--type-helper-text-01">{run.file_sha256}</span>
          </Stack>
          <HeadlineStrip run={run} />
          <div>
            <h2 className="cds--type-productive-heading-02">Price changes</h2>
            <ul>
              {PRICE_TIERS.map((tier) => (
                <li key={tier}>
                  {tier}: {run.summary.price_changes[tier] ?? 0}
                </li>
              ))}
            </ul>
          </div>
          <DataTable rows={entityRows} headers={[...ENTITY_HEADERS]}>
            {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Summary" description="Created and updated rows per entity">
                <Table {...getTableProps()}>
                  <TableHead>
                    <TableRow>
                      {headers.map((header) => {
                        const headerProps = getHeaderProps({ header });
                        const { key, ...rest } = headerProps;
                        return (
                          <TableHeader key={key} {...rest}>
                            {header.header}
                          </TableHeader>
                        );
                      })}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rows.map((row) => {
                      const rowProps = getRowProps({ row });
                      const { key, ...rest } = rowProps;
                      return (
                        <TableRow key={key} {...rest}>
                          {row.cells.map((cell) => (
                            <TableCell key={cell.id}>{cell.value}</TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
          <Stack orientation="horizontal" gap={4}>
            <Button kind="ghost" onClick={() => void downloadCin7Warnings(run.id)}>
              Download warnings ({run.warning_count})
            </Button>
            <Button kind="ghost" onClick={() => void downloadCin7Errors(run.id)}>
              Download errors ({run.error_count})
            </Button>
          </Stack>
        </Stack>
      ) : null}

      <DataTable rows={historyRows} headers={[...HISTORY_HEADERS]}>
        {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
          <TableContainer title="History" description="Past dry runs and commits">
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {headers.map((header) => {
                    const headerProps = getHeaderProps({ header });
                    const { key, ...rest } = headerProps;
                    return (
                      <TableHeader key={key} {...rest}>
                        {header.header}
                      </TableHeader>
                    );
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => {
                  const rowProps = getRowProps({ row });
                  const { key, ...rest } = rowProps;
                  return (
                    <TableRow key={key} {...rest}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>{cell.value}</TableCell>
                      ))}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>

      <Modal
        open={confirmOpen}
        danger
        modalHeading="Commit Cin7 import"
        primaryButtonText="Commit import"
        secondaryButtonText="Cancel"
        onRequestClose={() => setConfirmOpen(false)}
        onRequestSubmit={() => void commit()}
      >
        <p>
          This writes the dry run into the database. It is allowed only because this file had a
          completed dry run with no errors, and nothing has been imported since.
        </p>
      </Modal>
    </Stack>
  );
}
