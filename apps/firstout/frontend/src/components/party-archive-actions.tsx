"use client";

import {
  Button, InlineNotification, Modal, Tab, TabList, TabPanel, TabPanels, Tabs,
} from "@carbon/react";
import { Archive, Undo } from "@carbon/icons-react";
import { useEffect, useState, type ReactNode } from "react";
import type { ArchiveCounts } from "@/lib/api";
import styles from "./party-archive-actions.module.css";

export function PartyArchiveTabs({
  kind, archived, counts, onChange, children,
}: {
  kind: "customers" | "suppliers";
  archived: boolean;
  counts: ArchiveCounts | null;
  onChange: (archived: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className={styles.tabs}>
      <Tabs selectedIndex={archived ? 1 : 0} onChange={({ selectedIndex }) => onChange(selectedIndex === 1)}>
        <TabList aria-label={`${kind === "customers" ? "Customer" : "Supplier"} account status`}>
          <Tab>Active{counts ? ` (${counts.active})` : ""}</Tab>
          <Tab>Archived{counts ? ` (${counts.archived})` : ""}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>{!archived ? children : null}</TabPanel>
          <TabPanel>
            {archived ? <>
              <InlineNotification
                kind="info"
                title={`Archived ${kind} are preserved`}
                subtitle="Contacts, terms and available history stay linked. Restore an account to use it in new transactions."
                hideCloseButton
                lowContrast
                className={styles.notice}
              />
              {children}
            </> : null}
          </TabPanel>
        </TabPanels>
      </Tabs>
    </div>
  );
}

export function PartyArchiveAction({
  kind, name, archived, onConfirm, disabled = false,
}: {
  kind: "customer" | "supplier";
  name: string;
  archived: boolean;
  onConfirm: () => Promise<void>;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!open || busy) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault();setOpen(false); }
    };
    window.addEventListener("keydown", close, true);
    return () => window.removeEventListener("keydown", close, true);
  }, [open, busy]);
  async function confirm() {
    setBusy(true);setError(null);
    try { await onConfirm();setOpen(false); }
    catch (err) { setError(err instanceof Error ? err.message : `Could not ${archived ? "restore" : "archive"} ${kind}.`); }
    finally { setBusy(false); }
  }
  return <>
    <Button
      kind={archived ? "primary" : "tertiary"}
      renderIcon={archived ? Undo : Archive}
      disabled={disabled}
      onClick={() => { setError(null);setOpen(true); }}
    >{archived ? "Restore to active" : `Archive ${kind}`}</Button>
    {open ? <Modal
      open
      modalHeading={`${archived ? "Restore" : "Archive"} ${name}?`}
      primaryButtonText={busy ? "Saving…" : archived ? "Restore to active" : `Archive ${kind}`}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={busy}
      onRequestClose={() => { if (!busy) setOpen(false); }}
      onRequestSubmit={() => void confirm()}
      size="sm"
    >
      <p className={styles.confirmation}>{archived
        ? `This ${kind} will return to the active list and become available for new transactions.`
        : `This ${kind} will move to Archived and stay out of new transaction pickers. You can restore it at any time.`}</p>
      <p className={styles.confirmation}>Contacts, terms and available history stay linked. This does not create payments or change stock.</p>
      {error ? <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast /> : null}
    </Modal> : null}
  </>;
}
