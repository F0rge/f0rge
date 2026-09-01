"use client";

import {
  Button,
  ComboBox,
  ContentSwitcher,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextArea,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BinSelect } from "@/components/bin-select";
import { useLocationBins } from "@/hooks/use-location-bins";
import {
  ApiError,
  TRANSFER_STATUS_LABELS,
  canReceiveTransfer,
  canTransfer,
  cancelTransfer,
  createTransfer,
  dispatchTransfer,
  downloadTransferPdf,
  isActiveLocation,
  listInventory,
  listLocations,
  listSkus,
  listTransfers,
  receiveTransfer,
  type InventorySku,
  type Location,
  type Sku,
  type Transfer,
  type TransferStatus,
} from "@/lib/api";
import { optionalMovementBinId } from "@/lib/bin-helpers";
import { useAuth } from "@/lib/auth";

type ListTab = "draft" | "in_transit" | "received";

type DraftLine = {
  key: string;
  skuId: string;
  qty: number | "";
  fromBinId: string;
  toBinId: string;
};

const TAB_INDEX: Record<ListTab, number> = {
  draft: 0,
  in_transit: 1,
  received: 2,
};

const INDEX_TAB: ListTab[] = ["draft", "in_transit", "received"];

function newDraftLine(): DraftLine {
  return {
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    skuId: "",
    qty: 1,
    fromBinId: "",
    toBinId: "",
  };
}

function skuItemToString(item: Sku | null): string {
  if (!item) {
    return "";
  }
  return `${item.our_ref} — ${item.name}`;
}

function shouldFilterSku({
  item,
  itemToString,
  inputValue,
}: {
  item: Sku;
  itemToString?: (item: Sku | null) => string;
  inputValue: string | null;
}): boolean {
  if (!inputValue) {
    return true;
  }
  const haystack = (itemToString ?? skuItemToString)(item).toLowerCase();
  return haystack.includes(inputValue.toLowerCase());
}

function formatDateTime(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

function lineSummary(transfer: Transfer): string {
  if (transfer.lines.length === 0) {
    return "—";
  }
  return transfer.lines
    .map((line) => `${line.qty_dispatched} × ${line.sku_our_ref}`)
    .join(", ");
}

function statusTagType(status: TransferStatus): "blue" | "teal" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "in_transit") {
    return "teal";
  }
  if (status === "received") {
    return "green";
  }
  return "gray";
}

function matchesTab(status: TransferStatus, tab: ListTab): boolean {
  if (tab === "draft") {
    return status === "draft" || status === "cancelled";
  }
  return status === tab;
}

function fullQtyReceivePayload(transfer: Transfer) {
  return {
    lines: transfer.lines.map((line) => ({
      line_id: line.id,
      qty_received: line.qty_dispatched,
    })),
  };
}

function sourceOnHandForSku(
  inventoryBySku: Map<string, InventorySku>,
  skuId: string,
  locationId: string,
): number {
  return (
    inventoryBySku.get(skuId)?.locations.find((loc) => loc.location_id === locationId)?.on_hand ??
    0
  );
}

export default function TransfersPage() {
  const { user } = useAuth();
  const canXfer = canTransfer(user?.role);
  const canRecvXfer = canReceiveTransfer(user?.role);
  const canCancelInTransit = user?.role === "owner";

  const [tab, setTab] = useState<ListTab>("draft");
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [fromLocationId, setFromLocationId] = useState("");
  const [toLocationId, setToLocationId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([newDraftLine()]);
  const [inboundFilter, setInboundFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [locationData, skuData, inventoryData, transferData] = await Promise.all([
        listLocations(),
        listSkus(),
        listInventory(),
        listTransfers(),
      ]);
      setLocations(locationData.filter(isActiveLocation));
      setSkus(skuData);
      setInventory(inventoryData);
      setTransfers(transferData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transfers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const { activeBins: fromBins, defaultBinId: fromDefaultBinId } =
    useLocationBins(fromLocationId);
  const { activeBins: toBins, defaultBinId: toDefaultBinId } = useLocationBins(toLocationId);

  const inventoryBySku = useMemo(
    () => new Map(inventory.map((entry) => [entry.sku_id, entry])),
    [inventory],
  );

  const destinationOptions = locations.filter((loc) => loc.id !== fromLocationId);
  const sourceOptions = locations.filter((loc) => loc.id !== toLocationId);

  const skuOptions = skus.filter((sku) => {
    if (!fromLocationId) {
      return false;
    }
    return sourceOnHandForSku(inventoryBySku, sku.id, fromLocationId) > 0;
  });

  const formValid =
    Boolean(fromLocationId && toLocationId) &&
    lines.some((line) => {
      const qty = typeof line.qty === "number" ? line.qty : 0;
      return Boolean(line.skuId) && qty > 0;
    });

  const visibleTransfers = transfers.filter((entry) => {
    if (!matchesTab(entry.status, tab)) {
      return false;
    }
    if (tab === "in_transit" && inboundFilter && entry.to_location_id !== inboundFilter) {
      return false;
    }
    return true;
  });

  function updateLine(key: string, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  async function handleCreateDraft() {
    if (!canXfer || !formValid) {
      return;
    }
    const payloadLines = lines
      .map((line) => {
        const qty = typeof line.qty === "number" ? line.qty : 0;
        if (!line.skuId || qty <= 0) {
          return null;
        }
        return {
          sku_id: line.skuId,
          qty,
          from_bin_id: optionalMovementBinId(line.fromBinId, fromDefaultBinId),
          to_bin_id: optionalMovementBinId(line.toBinId, toDefaultBinId),
        };
      })
      .filter((line): line is NonNullable<typeof line> => line !== null);
    if (payloadLines.length === 0) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const created = await createTransfer({
        from_location_id: fromLocationId,
        to_location_id: toLocationId,
        notes,
        lines: payloadLines,
      });
      setSuccess(
        `${created.transfer_number} saved as draft. Destination stock is unchanged until the destination receives this transfer.`,
      );
      setLines([newDraftLine()]);
      setNotes("");
      setTab("draft");
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400)) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create transfer.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function runAction(id: string, work: () => Promise<string>) {
    setBusyId(id);
    setError(null);
    setSuccess(null);
    try {
      setSuccess(await work());
      await loadData();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 409 || err.status === 400 || err.status === 403)) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Transfer action failed.");
      }
    } finally {
      setBusyId(null);
    }
  }

  function handleDispatch(entry: Transfer) {
    void runAction(entry.id, async () => {
      const dispatched = await dispatchTransfer(entry.id);
      return `${dispatched.transfer_number} dispatched. Source stock decreased. Destination stock updates only after receive.`;
    });
  }

  function handleReceive(entry: Transfer) {
    void runAction(entry.id, async () => {
      const received = await receiveTransfer(entry.id, fullQtyReceivePayload(entry));
      const who = received.received_display_name ? ` Received by ${received.received_display_name}.` : "";
      return `${received.transfer_number} received. Destination stock updated.${who}`;
    });
  }

  function handleCancel(entry: Transfer) {
    void runAction(entry.id, async () => {
      const cancelled = await cancelTransfer(entry.id);
      return `${cancelled.transfer_number} cancelled.`;
    });
  }

  function handlePrint(entry: Transfer) {
    void runAction(entry.id, async () => {
      await downloadTransferPdf(entry.id, entry.transfer_number);
      return `Downloaded ${entry.transfer_number} transfer note.`;
    });
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Transfers</h1>
        <p className="cds--type-body-01">
          Internal stock moves are documents. Saving a draft does not move stock. Dispatch
          decreases source on-hand. Destination stock updates only after receive.
        </p>
      </div>

      {!canXfer && !canRecvXfer ? (
        <InlineNotification
          kind="info"
          title="View only"
          subtitle="You can list transfers and print notes. Create and dispatch need owner or warehouse. Receive needs owner, warehouse, or till."
          hideCloseButton
          lowContrast
        />
      ) : !canXfer ? (
        <InlineNotification
          kind="info"
          title="Inbound receive"
          subtitle="Till cannot create or dispatch. Open In transit to receive inbound transfers. Destination stock updates only after receive."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {success ? (
        <InlineNotification
          kind="success"
          title="Done"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {canXfer ? (
        <Stack gap={5}>
          <h2 className="cds--type-productive-heading-03">Create draft</h2>
          <p className="cds--type-body-01">
            Submit creates a transfer number only. Destination on-hand does not increase until
            receive.
          </p>
          <Select
            id="transfer-from"
            labelText="From location"
            value={fromLocationId}
            onChange={(event) => {
              setFromLocationId(event.target.value);
              setLines((current) =>
                current.map((line) => ({ ...line, skuId: "", fromBinId: "" })),
              );
            }}
          >
            <SelectItem value="" text="Select source location" />
            {sourceOptions.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          <Select
            id="transfer-to"
            labelText="To location"
            value={toLocationId}
            onChange={(event) => {
              setToLocationId(event.target.value);
              setLines((current) => current.map((line) => ({ ...line, toBinId: "" })));
            }}
          >
            <SelectItem value="" text="Select destination location" />
            {destinationOptions.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          <TextArea
            id="transfer-notes"
            labelText="Notes (optional)"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
          {lines.map((line, index) => {
            const selectedSku = skuOptions.find((sku) => sku.id === line.skuId) ?? null;
            const onHand = line.skuId
              ? sourceOnHandForSku(inventoryBySku, line.skuId, fromLocationId)
              : 0;
            const numericQty = typeof line.qty === "number" ? line.qty : 0;
            return (
              <Stack key={line.key} gap={4}>
                <h3 className="cds--type-productive-heading-01">Line {index + 1}</h3>
                <ComboBox
                  id={`transfer-line-sku-${line.key}`}
                  titleText="SKU"
                  placeholder="Type to search..."
                  items={skuOptions}
                  itemToString={skuItemToString}
                  shouldFilterItem={shouldFilterSku}
                  selectedItem={selectedSku}
                  onChange={({ selectedItem }) =>
                    updateLine(line.key, { skuId: selectedItem?.id ?? "" })
                  }
                  helperText={
                    fromLocationId
                      ? line.skuId
                        ? `${onHand} on hand at source`
                        : "Only SKUs with on-hand stock at the source are listed"
                      : "Choose a source location first"
                  }
                  disabled={!fromLocationId}
                />
                <NumberInput
                  id={`transfer-line-qty-${line.key}`}
                  label="Quantity"
                  min={1}
                  value={line.qty}
                  onChange={(_event, { value }) => {
                    updateLine(line.key, { qty: value === "" ? "" : Number(value) });
                  }}
                  invalid={numericQty > onHand && onHand > 0}
                  invalidText={`Only ${onHand} available at source`}
                  disabled={!line.skuId}
                />
                {fromLocationId ? (
                  <BinSelect
                    id={`transfer-line-from-bin-${line.key}`}
                    labelText="From bin (optional)"
                    value={line.fromBinId}
                    bins={fromBins}
                    onChange={(fromBinId) => updateLine(line.key, { fromBinId })}
                    helperText="Leave as default to use the location default bin."
                  />
                ) : null}
                {toLocationId ? (
                  <BinSelect
                    id={`transfer-line-to-bin-${line.key}`}
                    labelText="To bin (optional)"
                    value={line.toBinId}
                    bins={toBins}
                    onChange={(toBinId) => updateLine(line.key, { toBinId })}
                    helperText="Leave as default to use the location default bin."
                  />
                ) : null}
                {lines.length > 1 ? (
                  <Button
                    kind="ghost"
                    size="sm"
                    onClick={() => setLines((current) => current.filter((row) => row.key !== line.key))}
                  >
                    Remove line
                  </Button>
                ) : null}
              </Stack>
            );
          })}
          <Button kind="ghost" size="sm" onClick={() => setLines((current) => [...current, newDraftLine()])}>
            Add line
          </Button>
          <Button disabled={submitting || !formValid} onClick={() => void handleCreateDraft()}>
            {submitting ? "Saving…" : "Save draft"}
          </Button>
        </Stack>
      ) : null}

      <ContentSwitcher
        selectedIndex={TAB_INDEX[tab]}
        onChange={(event) => {
          const index = event.index ?? 0;
          setTab(INDEX_TAB[index] ?? "draft");
        }}
      >
        <Switch name="draft" text="Draft" />
        <Switch name="in_transit" text="In transit" />
        <Switch name="received" text="Received" />
      </ContentSwitcher>

      {tab === "in_transit" ? (
        <Select
          id="transfer-inbound-filter"
          labelText="Destination"
          value={inboundFilter}
          onChange={(event) => setInboundFilter(event.target.value)}
        >
          <SelectItem value="" text="All destinations" />
          {locations.map((entry) => (
            <SelectItem key={entry.id} value={entry.id} text={entry.name} />
          ))}
        </Select>
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading…</p>
      ) : visibleTransfers.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No transfers"
          subtitle={
            tab === "draft"
              ? "No draft or cancelled transfers."
              : tab === "in_transit"
                ? "No inbound transfers in transit."
                : "No received transfers yet."
          }
          hideCloseButton
          lowContrast
        />
      ) : (
        <TableContainer
          title={tab === "draft" ? "Drafts" : tab === "in_transit" ? "In transit" : "Received"}
          description={
            tab === "in_transit"
              ? "Receive full dispatched qty. Destination stock updates only after receive."
              : tab === "received"
                ? "Print the transfer note to see who received."
                : "Cancelled transfers stay on this tab. Dispatch decreases source stock only."
          }
        >
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Number</TableHeader>
                <TableHeader>From</TableHeader>
                <TableHeader>To</TableHeader>
                <TableHeader>Lines</TableHeader>
                <TableHeader>Status</TableHeader>
                <TableHeader>{tab === "received" ? "Received" : "Updated"}</TableHeader>
                <TableHeader>Actions</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {visibleTransfers.map((entry) => {
                const busy = busyId === entry.id;
                return (
                  <TableRow key={entry.id}>
                    <TableCell>{entry.transfer_number}</TableCell>
                    <TableCell>{entry.from_location_name}</TableCell>
                    <TableCell>{entry.to_location_name}</TableCell>
                    <TableCell>{lineSummary(entry)}</TableCell>
                    <TableCell>
                      <Tag type={statusTagType(entry.status)}>
                        {TRANSFER_STATUS_LABELS[entry.status]}
                      </Tag>
                    </TableCell>
                    <TableCell>
                      {tab === "received"
                        ? `${formatDateTime(entry.received_at)}${
                            entry.received_display_name ? ` · ${entry.received_display_name}` : ""
                          }`
                        : formatDateTime(entry.updated_at)}
                    </TableCell>
                    <TableCell>
                      <Stack gap={3} orientation="horizontal">
                        {entry.status === "draft" && canXfer ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleDispatch(entry)}
                          >
                            Dispatch
                          </Button>
                        ) : null}
                        {entry.status === "in_transit" && canRecvXfer ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleReceive(entry)}
                          >
                            Receive
                          </Button>
                        ) : null}
                        {entry.status !== "cancelled" ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handlePrint(entry)}
                          >
                            Print PDF
                          </Button>
                        ) : null}
                        {entry.status === "draft" && canXfer ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleCancel(entry)}
                          >
                            Cancel
                          </Button>
                        ) : null}
                        {entry.status === "in_transit" && canCancelInTransit ? (
                          <Button
                            kind="ghost"
                            size="sm"
                            disabled={busy}
                            onClick={() => handleCancel(entry)}
                          >
                            Cancel
                          </Button>
                        ) : null}
                      </Stack>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  );
}
