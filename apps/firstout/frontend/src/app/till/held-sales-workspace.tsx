import { useEffect, useRef, useState } from "react";
import {
  Button, InlineNotification, Modal, Search, Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow, TableSelectAll, TableSelectRow, Tag, TextArea,
} from "@carbon/react";
import { ArrowRight, Edit, Renew, TrashCan } from "@carbon/icons-react";

import {
  ApiError, deleteTillHeldSales, formatZarAmount, listHeldSales, updateHeldSaleNote, type HeldSale,
} from "@/lib/api";
import { formatQuantity } from "@/lib/quantity";

import "./held-sales.css";

function savedTime(value: string): string {
  const timestamp = new Date(/(?:z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`);
  return new Intl.DateTimeFormat("en-ZA", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(timestamp);
}

export function useHeldSales(locationId: string) {
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<{
    locationId: string; revision: number; sales: HeldSale[]; error?: string;
  } | null>(null);
  const current = result?.locationId === locationId ? result : null;
  const loading = Boolean(locationId && (!current || current.revision !== revision));
  useEffect(() => {
    if (!locationId) return;
    const controller = new AbortController();
    void listHeldSales(locationId, controller.signal).then((sales) => {
      if (!controller.signal.aborted) setResult({ locationId, revision, sales });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setResult({
        locationId, revision, sales: [],
        error: error instanceof Error ? error.message : "Could not load held sales.",
      });
    });
    return () => controller.abort();
  }, [locationId, revision]);
  return {
    sales: current?.sales ?? [],
    error: current?.error,
    loading,
    refresh: () => setRevision((value) => value + 1),
  };
}

type HeldSalesWorkspaceProps = {
  locationId: string;
  showroom: string;
  list: ReturnType<typeof useHeldSales>;
  focusId: string;
  busy: boolean;
  onBusy: (busy: boolean) => void;
  onResume: (draft: HeldSale) => void;
  onNotice: (title: string, subtitle?: string) => void;
};

type DeletePrompt = { kind: "one" | "selected" | "all"; drafts: HeldSale[] };
const amount = (value: string | null) => value === null ? "—" : formatZarAmount(value);

export function HeldSalesWorkspace({
  locationId, showroom, list, focusId, busy, onBusy, onResume, onNotice,
}: HeldSalesWorkspaceProps) {
  const [query, setQuery] = useState("");
  const [newestFirst, setNewestFirst] = useState(true);
  const [selected, setSelected] = useState(focusId);
  const [checked, setChecked] = useState<string[]>([]);
  const [deletePrompt, setDeletePrompt] = useState<DeletePrompt | null>(null);
  const [noteDraft, setNoteDraft] = useState<{ draft: HeldSale; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestInProgress = useRef(false);
  const queryText = query.toLowerCase().trim();
  const filtered = list.sales.filter((sale) => [
    sale.reference, sale.customer_name, sale.note, ...sale.lines.map((line) => `${line.sku_code} ${line.sku_name}`),
  ].join(" ").toLowerCase().includes(queryText))
    .sort((a, b) => newestFirst ? b.held_at.localeCompare(a.held_at) : a.held_at.localeCompare(b.held_at));
  const draft = filtered.find((sale) => sale.id === selected) ?? filtered[0];
  const checkedDrafts = filtered.filter((sale) => checked.includes(sale.id));
  const allChecked = filtered.length > 0 && checkedDrafts.length === filtered.length;
  const disabled = busy || list.loading || Boolean(list.error);
  const count = deletePrompt?.drafts.length ?? 0;
  const deleteTitle = deletePrompt?.kind === "all" ? "Delete all held sales?" :
    deletePrompt?.kind === "one" ? `Delete ${deletePrompt.drafts[0].reference}?` :
      `Delete ${count} selected ${count === 1 ? "sale" : "sales"}?`;

  function selectRow(id: string) {
    setChecked((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }

  async function runAction(callback: () => Promise<void>) {
    if (requestInProgress.current || busy) return;
    requestInProgress.current = true;
    onBusy(true);
    setError(null);
    try {
      await callback();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not update held sales.");
    } finally {
      requestInProgress.current = false;
      onBusy(false);
    }
  }

  return <>
    <section className="held-workspace">
      <div className="held-workspace-main">
        <div className="held-workspace-header">
          <div><h2>Held sales</h2><p>{showroom || "Choose a showroom in Current sale"}{locationId && ` · ${list.sales.length} on hold`}</p></div>
          {locationId && <Button kind="ghost" size="sm" renderIcon={Renew}
            disabled={busy || list.loading} onClick={list.refresh}>Refresh</Button>}
        </div>
        {list.error && <InlineNotification kind="error" title="Could not load held sales" subtitle={list.error} lowContrast hideCloseButton />}
        {error && !deletePrompt && !noteDraft && <InlineNotification kind="error" title="Held sales changed"
          subtitle={error} lowContrast onCloseButtonClick={() => setError(null)} />}
        <div className="held-toolbar">
          <Search id="held-search" size="lg" labelText="Search held sales" placeholder="Customer, reference, product or note"
            value={query} onChange={(event) => { setQuery(event.target.value); setChecked([]); }} />
          <Button kind="danger--ghost" renderIcon={TrashCan} disabled={disabled || !list.sales.length}
            onClick={() => { setError(null); setDeletePrompt({ kind: "all", drafts: list.sales }); }}>Delete all</Button>
        </div>
        {checkedDrafts.length > 0 && <div className="held-selection-bar">
          <strong aria-live="polite">{checkedDrafts.length} selected</strong>
          <div>
            <Button size="sm" kind="ghost" renderIcon={TrashCan} disabled={disabled}
              onClick={() => { setError(null); setDeletePrompt({ kind: "selected", drafts: checkedDrafts }); }}>Delete selected</Button>
            <Button size="sm" kind="ghost" onClick={() => setChecked([])}>Clear selection</Button>
          </div>
        </div>}
        {list.loading && <div className="held-empty" role="status">Loading held sales…</div>}
        {!list.loading && !list.error && filtered.length === 0 && <div className="held-empty">
          <h3>{queryText ? "No matching sales" : "No held sales at this showroom"}</h3>
          <p>{queryText ? "Try a different search." : "Use Hold sale to save a basket for later."}</p>
        </div>}
        {filtered.length > 0 && <div className="held-table-scroll">
          <Table size="lg" aria-label="Held baskets">
            <TableHead><TableRow>
              <TableSelectAll id="held-select-all" name="held-select-all" aria-label="Select all visible sales"
                checked={allChecked} indeterminate={checkedDrafts.length > 0 && !allChecked}
                onSelect={() => setChecked(allChecked ? [] : filtered.map((sale) => sale.id))} />
              <TableHeader>Sale</TableHeader><TableHeader>Customer</TableHeader>
              <TableHeader isSortable isSortHeader sortDirection={newestFirst ? "DESC" : "ASC"}
                onClick={() => setNewestFirst(!newestFirst)}>Held at</TableHeader>
              <TableHeader>Est. total</TableHeader>
            </TableRow></TableHead>
            <TableBody>{filtered.map((entry) => <TableRow key={entry.id} className={entry.id === draft?.id ? "held-table-selected" : ""}>
              <TableSelectRow id={`held-${entry.id}`} name={entry.id} aria-label={`Select ${entry.reference}`}
                checked={checked.includes(entry.id)} onSelect={() => selectRow(entry.id)} />
              <TableCell><button type="button" className="held-table-link" aria-pressed={entry.id === draft?.id}
                onClick={() => setSelected(entry.id)}>{entry.reference}</button></TableCell>
              <TableCell>{entry.customer_name}</TableCell>
              <TableCell className="held-table-time">{savedTime(entry.held_at)}</TableCell>
              <TableCell>{amount(entry.estimated_total_inc_vat)}</TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </div>}
      </div>
      {draft && <aside className="held-detail" aria-label="Held basket details">
        <div className="held-detail-title">
          <span className="held-code">{draft.reference}</span><Tag size="sm" type="warm-gray">On hold</Tag>
        </div>
        <h2>{draft.customer_name}</h2>
        <p className="held-detail-meta">Held {savedTime(draft.held_at)} · {draft.held_by_name}</p>
        <h3 className="held-product-heading">{draft.lines.length} product {draft.lines.length === 1 ? "line" : "lines"}</h3>
        <ul className="held-detail-products">{draft.lines.map((line, index) => <li key={`${line.sku_id}-${index}`}>
          <div><strong>{line.sku_name}</strong><span>{line.sku_code} · Qty {formatQuantity(line.qty)}{Number(line.discount_percent) > 0 && ` · ${Number(line.discount_percent)}% off`}</span></div>
          <span>{amount(line.estimated_total_inc_vat)}</span>
        </li>)}</ul>
        <div className="held-detail-total"><span>Est. total incl. VAT</span><strong>{amount(draft.estimated_total_inc_vat)}</strong></div>
        <div className="held-note">
          {draft.note && <p>{draft.note}</p>}
          <Button kind="ghost" size="sm" renderIcon={Edit} disabled={disabled}
            onClick={() => { setError(null); setNoteDraft({ draft, text: draft.note ?? "" }); }}>{draft.note ? "Edit note" : "Add note"}</Button>
        </div>
        <div className="held-detail-actions">
          <Button className="held-primary" renderIcon={ArrowRight} disabled={disabled} onClick={() => onResume(draft)}>Resume sale</Button>
          <Button kind="danger--ghost" renderIcon={TrashCan} disabled={disabled}
            onClick={() => { setError(null); setDeletePrompt({ kind: "one", drafts: [draft] }); }}>Delete sale</Button>
        </div>
      </aside>}
    </section>
    <Modal open={deletePrompt !== null} danger modalHeading={deleteTitle}
      primaryButtonText={busy ? "Deleting…" : "Delete permanently"} primaryButtonDisabled={busy}
      secondaryButtonText="Cancel" selectorPrimaryFocus=".cds--modal-footer .cds--btn--secondary"
      shouldSubmitOnEnter={false} preventCloseOnClickOutside
      onRequestClose={() => { if (!busy) setDeletePrompt(null); }} onRequestSubmit={() => {
        if (!deletePrompt) return;
        void runAction(async () => {
          try {
            const result = await deleteTillHeldSales(locationId, deletePrompt.drafts.map((sale) => sale.id), deletePrompt.kind === "all");
            onNotice(result.deleted_count === 1 ? `${deletePrompt.drafts[0].reference} permanently deleted` : `${result.deleted_count} held sales permanently deleted`);
            if (deletePrompt.kind === "all") setQuery("");
            setChecked([]);
            setDeletePrompt(null);
          } catch (failure) {
            if (failure instanceof ApiError && failure.status === 409) {
              setDeletePrompt(null);
              setChecked([]);
            }
            throw failure;
          } finally {
            list.refresh();
          }
        });
      }}>
      {error && deletePrompt && <InlineNotification kind="error" title="Could not delete held sales" subtitle={error} lowContrast hideCloseButton />}
      <p>{deletePrompt?.kind === "all"
        ? `This permanently deletes ${count} ${count === 1 ? "held sale" : "held sales"} at ${showroom}.${queryText ? " This includes sales outside your search results." : ""}`
        : count === 1 ? "This permanently deletes the held basket." : `This permanently deletes the ${count} selected baskets.`
      }</p>
    </Modal>
    <Modal open={noteDraft !== null} modalHeading={`Note for ${noteDraft?.draft.reference ?? "held sale"}`}
      primaryButtonText={busy ? "Saving…" : "Save note"} primaryButtonDisabled={busy}
      secondaryButtonText="Cancel" selectorPrimaryFocus="#held-note" preventCloseOnClickOutside
      onRequestClose={() => { if (!busy) setNoteDraft(null); }} onRequestSubmit={() => {
        if (!noteDraft) return;
        void runAction(async () => {
          try {
            await updateHeldSaleNote(noteDraft.draft.id, locationId, noteDraft.draft.version, noteDraft.text.trim() || null);
          } catch (failure) {
            if (failure instanceof ApiError && failure.status === 409) {
              setNoteDraft(null);
              list.refresh();
            }
            throw failure;
          }
          setNoteDraft(null);
          list.refresh();
          onNotice("Note saved");
        });
      }}>
      {error && noteDraft && <InlineNotification kind="error" title="Could not save note" subtitle={error} lowContrast hideCloseButton />}
      <TextArea id="held-note" labelText="Staff note" rows={3} disabled={busy}
        value={noteDraft?.text ?? ""} maxLength={500} maxCount={500} enableCounter
        onChange={(event) => { if (noteDraft) setNoteDraft({ ...noteDraft, text: event.target.value }); }} />
    </Modal>
  </>;
}
