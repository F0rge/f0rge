import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  Button, ButtonSet, Dropdown, InlineLoading, InlineNotification, Stack, Table, TableBody, TableCell,
  TableContainer, TableHead, TableHeader, TableRow, Tag, Tile,
} from "@carbon/react";
import { Edit, Information } from "@carbon/icons-react";

import {
  ApiError, confirmPick, downloadPickPdf, getPick, getPickDefaultAllocations, listLocations, updatePick,
  type Location, type PickDefaultAllocations, type PickDocument, type UpdatePickPayload,
} from "@/lib/api";
import { PICK_STATUS_LABELS, pickStatusTagType } from "@/lib/picks";
import { formatQuantity } from "@/lib/quantity";
import {
  confirmedTitle, defaultsPatch, isLineChanged, lineDefaults, noStockNote, sourceOptionText,
  sourcePatch, sources, whatHappensNext,
} from "@/lib/till-pick-list";

import "./pick-list.css";

type SourceOption = { id: string; text: string; disabled: boolean };

type TillPickListProps = {
  pickId: string;
  /** The till's showroom: its stock was deducted at the sale, so it is only a source if stock is left. */
  showroomId: string;
  /** "Name (OUR-REF)" for each No stock needed line in the sale. */
  noStockLabels: string[];
  onNewSale: () => void;
};

const messageOf = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback);

/** The sale's draft pick for off-site lines: choose sources, confirm, then see what happens next. */
export function TillPickList({
  pickId, showroomId, noStockLabels, onNewSale,
}: TillPickListProps) {
  const [pick, setPick] = useState<PickDocument | null>(null);
  const [defaults, setDefaults] = useState<PickDefaultAllocations | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openSku, setOpenSku] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [loaded, locationData] = await Promise.all([getPick(pickId), listLocations()]);
        if (cancelled) return;
        setPick(loaded);
        setLocations(locationData);
        if (loaded.status === "draft") {
          const next = await getPickDefaultAllocations(pickId);
          if (!cancelled) setDefaults(next);
        }
      } catch (err) {
        if (!cancelled) setError(messageOf(err, "Could not load the pick list."));
      }
    })();
    return () => { cancelled = true; };
  }, [pickId]);

  const locationTypes = useMemo(() => new Map(locations.map((loc) => [loc.id, loc.type])), [locations]);

  async function save(body: UpdatePickPayload) {
    setBusy(true);
    setError(null);
    try {
      setPick(await updatePick(pickId, body));
    } catch (err) {
      setError(messageOf(err, "Could not change the source."));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      setPick(await confirmPick(pickId));
    } catch (err) {
      // 409 detail names the short line, e.g. "Insufficient stock for SOFA-1 at Warehouse".
      setError(messageOf(err, "Could not confirm the pick list."));
      if (err instanceof ApiError && err.status === 409) {
        // Fresh on-hand so the cashier can choose another source.
        void getPick(pickId).then(setPick).catch(() => undefined);
      }
    } finally {
      setBusy(false);
    }
  }

  async function printSlip() {
    if (!pick) return;
    setError(null);
    try {
      await downloadPickPdf(pick.id, pick.pick_number || "pick");
    } catch (err) {
      setError(messageOf(err, "Could not print the pick slip."));
    }
  }

  const errorNote = error ? (
    <InlineNotification kind="error" lowContrast title="Pick list" subtitle={error}
      onCloseButtonClick={() => setError(null)} />
  ) : null;
  const quietNote = noStockNote(noStockLabels);
  const openLine = pick?.lines.find((line) => line.sku_id === openSku);
  // ponytail: Carbon's sm menu is 2rem per item, capped at 5.5 items; the table grows by that while a menu is open.
  const menuSpace = { "--till-pick-menu-space": `${Math.min(openLine?.allocations.length ?? 0, 5.5) * 2}rem` } as CSSProperties;

  return (
    <section id="pick-list" aria-labelledby="till-pick-list-title" className="till-pick-list">
      <Tile className="firstout-tax-invoice">
        {!pick ? (
          errorNote ?? <InlineLoading description="Loading the pick list…" />
        ) : (
          <Stack gap={5}>
            <div className="till-pick-list__header">
              <div>
                <h2 id="till-pick-list-title">Pick list {pick.pick_number}</h2>
                <p className="cds--type-helper-text-01 till-pick-list__quiet">
                  Only items from other locations. Stock at this showroom was taken at the sale.
                </p>
              </div>
              <Tag type={pickStatusTagType(pick.status)}>{PICK_STATUS_LABELS[pick.status]}</Tag>
            </div>
            {errorNote}

            {pick.status === "draft" ? (
              <>
                <div className={openLine ? "till-pick-list__table till-pick-list__table--menu-open" : "till-pick-list__table"}
                  style={menuSpace}>
                  <TableContainer>
                    <Table size="sm">
                      <TableHead>
                        <TableRow>
                          <TableHeader>SKU</TableHeader>
                          <TableHeader>Description</TableHeader>
                          <TableHeader>Qty</TableHeader>
                          <TableHeader>Source location</TableHeader>
                          <TableHeader>On hand at source</TableHeader>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {pick.lines.map((line) => {
                          const current = sources(line);
                          const lineDefs = lineDefaults(defaults, line.sku_id);
                          const defaultIds = new Set(lineDefs.map((entry) => entry.location_id));
                          const options: SourceOption[] = line.allocations.map((cell) => ({
                            id: cell.location_id,
                            text: sourceOptionText(cell, {
                              isDefault: defaultIds.has(cell.location_id),
                              isShowroom: cell.location_id === showroomId,
                            }),
                            // The whole line comes from one source here, so it needs the full qty.
                            disabled: cell.location_id !== current[0]?.location_id && cell.on_hand < line.qty_needed,
                          }));
                          const selected = current.length === 1
                            ? options.find((option) => option.id === current[0].location_id)
                            : undefined;
                          return (
                            <TableRow key={line.sku_id}>
                              <TableCell>{line.sku_our_ref}</TableCell>
                              <TableCell>{line.sku_name}</TableCell>
                              <TableCell>{formatQuantity(line.qty_needed)}</TableCell>
                              <TableCell className="till-pick-list__source">
                                {current.length > 1 ? (
                                  <>
                                    <p>{current.map((cell) => `${cell.location_name} ×${formatQuantity(cell.qty)}`).join(", ")}</p>
                                    <p className="cds--type-helper-text-01 till-pick-list__quiet">
                                      Split across locations. Change it in Picks.
                                    </p>
                                  </>
                                ) : (
                                  <Dropdown<SourceOption>
                                    id={`till-pick-source-${line.sku_id}`}
                                    titleText={`Source location for ${line.sku_our_ref}`}
                                    hideLabel
                                    label="Choose a source"
                                    size="sm"
                                    items={options}
                                    itemToString={(option) => option?.text ?? ""}
                                    selectedItem={selected}
                                    disabled={busy}
                                    downshiftProps={{
                                      onIsOpenChange: ({ isOpen }) => setOpenSku(isOpen ? line.sku_id : null),
                                    }}
                                    onChange={({ selectedItem }) => {
                                      if (selectedItem && selectedItem.id !== current[0]?.location_id) {
                                        void save(sourcePatch(pick.lines, line.sku_id, selectedItem.id));
                                      }
                                    }}
                                  />
                                )}
                                {isLineChanged(line, defaults) && (
                                  <div className="till-pick-list__changed">
                                    <Tag type="purple" size="sm" renderIcon={Edit}>Changed</Tag>
                                    <span className="cds--type-helper-text-01">
                                      Default: {lineDefs.map((entry) => entry.location_name).join(", ") || "none"}
                                    </span>
                                  </div>
                                )}
                              </TableCell>
                              <TableCell>
                                {current.map((cell) => formatQuantity(cell.on_hand)).join(" · ") || "—"}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </div>
                {quietNote && <p className="cds--type-helper-text-01 till-pick-list__quiet">{quietNote}</p>}
                <div>
                  <ButtonSet>
                    <Button kind="secondary" disabled={busy || !defaults}
                      onClick={() => defaults && void save(defaultsPatch(pick.lines, defaults))}>
                      Reset to defaults
                    </Button>
                    <Button kind="primary" disabled={busy} onClick={() => void confirm()}>
                      Confirm pick list
                    </Button>
                  </ButtonSet>
                  <p className="cds--type-helper-text-01 till-pick-list__quiet till-pick-list__hint">
                    Not ready? The draft stays in Picks.
                  </p>
                </div>
              </>
            ) : pick.status === "cancelled" ? (
              <p className="cds--type-body-01">This pick was cancelled in Picks.</p>
            ) : (
              <>
                <InlineNotification kind="success" lowContrast hideCloseButton
                  title={confirmedTitle(pick.pick_number, pick.lines)} />
                <div className="till-pick-list__next">
                  <h3 className="cds--type-heading-compact-01">What happens next</h3>
                  <ul>
                    {whatHappensNext(pick.lines, locationTypes, showroomId).map((step) => (
                      <li key={step.locationId}>
                        <strong>{step.heading}</strong>: {step.detail}
                      </li>
                    ))}
                  </ul>
                  <p className="cds--type-body-compact-01">
                    Completing the pick in Picks stages it and creates the delivery for this invoice.
                  </p>
                </div>
                <p className="cds--type-helper-text-01 till-pick-list__quiet till-pick-list__info">
                  <Information size={16} aria-hidden />
                  Picking happens after the sale and does not hold up the till.
                </p>
                <div className="firstout-catalogue-actions">
                  <Button kind="primary" onClick={onNewSale}>New sale</Button>
                  <Button kind="secondary" href={`/picks/${pick.id}`}>Open pick</Button>
                  <Button kind="tertiary" onClick={() => void printSlip()}>Print pick slip</Button>
                </div>
              </>
            )}
          </Stack>
        )}
      </Tile>
    </section>
  );
}
