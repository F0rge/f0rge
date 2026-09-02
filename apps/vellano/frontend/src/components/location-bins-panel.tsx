"use client";

import {
  Button,
  Checkbox,
  InlineNotification,
  Modal,
  NumberInput,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
} from "@carbon/react";
import { useMemo, useState } from "react";

import { ApiError, createLocationBin, generateLocationBinGrid, updateLocationBin } from "@/lib/api";
import type { Location } from "@/lib/api";
import { parseRowCodes, sortLocationBins } from "@/lib/bin-helpers";
import { printBinLabels } from "@/lib/print-bin-labels";
import { useLocationBins } from "@/hooks/use-location-bins";

type LocationBinsPanelProps = {
  location: Location;
  canMutate: boolean;
};

export function LocationBinsPanel({ location, canMutate }: LocationBinsPanelProps) {
  const { bins, loading, error, reload } = useLocationBins(location.id);
  const [panelError, setPanelError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [saving, setSaving] = useState(false);
  const [gridOpen, setGridOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [gridRows, setGridRows] = useState("A–B");
  const [gridBays, setGridBays] = useState<number | "">(12);
  const [gridLevels, setGridLevels] = useState<number | "">(4);
  const [createRow, setCreateRow] = useState("");
  const [createBay, setCreateBay] = useState<number | "">(1);
  const [createLevel, setCreateLevel] = useState<number | "">(1);

  const sorted = useMemo(() => sortLocationBins(bins), [bins]);
  const parsedRows = parseRowCodes(gridRows);
  const bayCount = typeof gridBays === "number" ? gridBays : 0;
  const levelCount = typeof gridLevels === "number" ? gridLevels : 0;
  const gridValid = parsedRows.length > 0 && bayCount >= 1 && levelCount >= 1;
  const createValid =
    createRow.trim().length > 0 &&
    typeof createBay === "number" &&
    createBay >= 1 &&
    typeof createLevel === "number" &&
    createLevel >= 1;

  function toggleSelect(binId: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(binId)) {
        next.delete(binId);
      } else {
        next.add(binId);
      }
      return next;
    });
  }

  function handlePrint() {
    const selected = sorted.filter((bin) => selectedIds.has(bin.id) && !bin.is_archived);
    printBinLabels(selected.length > 0 ? selected : sorted.filter((bin) => !bin.is_archived));
  }

  async function handleGenerate() {
    if (!gridValid) {
      return;
    }
    setSaving(true);
    setPanelError(null);
    setSuccess(null);
    try {
      const result = await generateLocationBinGrid(location.id, {
        rows: parsedRows,
        bays: bayCount,
        levels: levelCount,
      });
      const sample = result
        .filter((bin) => parsedRows.includes(bin.row_code))
        .map((bin) => bin.code);
      const preview = [sample[0], sample.find((code) => code.endsWith("-12-3")), sample[sample.length - 1]]
        .filter((code): code is string => Boolean(code))
        .filter((code, index, all) => all.indexOf(code) === index);
      setSuccess(
        `Grid ready for ${location.name}. ${result.length} bins. Codes include ${preview.join(", ") || "FLOOR"}.`,
      );
      setGridOpen(false);
      await reload();
    } catch (err) {
      setPanelError(err instanceof Error ? err.message : "Failed to generate bin grid.");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreate() {
    if (!createValid || typeof createBay !== "number" || typeof createLevel !== "number") {
      return;
    }
    setSaving(true);
    setPanelError(null);
    setSuccess(null);
    try {
      const created = await createLocationBin(location.id, {
        row_code: createRow.trim(),
        bay: createBay,
        level: createLevel,
      });
      setSuccess(`Created bin ${created.code}.`);
      setCreateOpen(false);
      setCreateRow("");
      setCreateBay(1);
      setCreateLevel(1);
      await reload();
    } catch (err) {
      setPanelError(err instanceof Error ? err.message : "Failed to create bin.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePatch(binId: string, payload: { is_archived?: boolean; is_default?: boolean }) {
    setSaving(true);
    setPanelError(null);
    try {
      await updateLocationBin(location.id, binId, payload);
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setPanelError(err.message);
      } else {
        setPanelError(err instanceof Error ? err.message : "Failed to update bin.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={4}>
      <div className="vellano-page-header">
        <p className="cds--type-body-01">
          Bins at <strong>{location.name}</strong>
        </p>
        <Stack gap={3} orientation="horizontal">
          {canMutate ? (
            <>
              <Button kind="secondary" size="sm" onClick={() => setGridOpen(true)}>
                Generate grid
              </Button>
              <Button kind="ghost" size="sm" onClick={() => setCreateOpen(true)}>
                Add bin
              </Button>
            </>
          ) : null}
          <Button kind="ghost" size="sm" onClick={handlePrint} disabled={sorted.length === 0}>
            Print labels
          </Button>
        </Stack>
      </div>

      {error || panelError ? (
        <InlineNotification
          kind="error"
          title="Bins"
          subtitle={panelError ?? error ?? ""}
          onCloseButtonClick={() => setPanelError(null)}
          lowContrast
        />
      ) : null}
      {success ? (
        <InlineNotification
          kind="success"
          title="Bins"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading bins…</p>
      ) : sorted.length === 0 ? (
        <p className="cds--type-body-01">No bins at this location.</p>
      ) : (
        <Table size="sm">
          <TableHead>
            <TableRow>
              <TableHeader />
              <TableHeader>Code</TableHeader>
              <TableHeader>Row</TableHeader>
              <TableHeader>Bay</TableHeader>
              <TableHeader>Level</TableHeader>
              <TableHeader>Default</TableHeader>
              <TableHeader>Archived</TableHeader>
              {canMutate ? <TableHeader>Actions</TableHeader> : null}
            </TableRow>
          </TableHead>
          <TableBody>
            {sorted.map((bin) => (
              <TableRow key={bin.id}>
                <TableCell>
                  <Checkbox
                    id={`bin-select-${bin.id}`}
                    labelText={`Select ${bin.code}`}
                    hideLabel
                    disabled={bin.is_archived}
                    checked={selectedIds.has(bin.id)}
                    onChange={() => toggleSelect(bin.id)}
                  />
                </TableCell>
                <TableCell>
                  <span style={{ fontFamily: "IBM Plex Mono, monospace" }}>{bin.code}</span>
                </TableCell>
                <TableCell>{bin.row_code}</TableCell>
                <TableCell>{bin.bay}</TableCell>
                <TableCell>{bin.level}</TableCell>
                <TableCell>
                  {bin.is_default ? (
                    <Tag type="blue" size="sm">
                      Default
                    </Tag>
                  ) : (
                    "—"
                  )}
                </TableCell>
                <TableCell>{bin.is_archived ? "Archived" : "Active"}</TableCell>
                {canMutate ? (
                  <TableCell>
                    <Stack gap={3} orientation="horizontal">
                      {!bin.is_default && !bin.is_archived ? (
                        <Button
                          kind="ghost"
                          size="sm"
                          disabled={saving}
                          onClick={() => void handlePatch(bin.id, { is_default: true })}
                        >
                          Set default
                        </Button>
                      ) : null}
                      {!bin.is_archived ? (
                        <Button
                          kind="danger--ghost"
                          size="sm"
                          disabled={saving}
                          onClick={() => void handlePatch(bin.id, { is_archived: true })}
                        >
                          Archive
                        </Button>
                      ) : null}
                    </Stack>
                  </TableCell>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <Modal
        open={gridOpen}
        modalHeading={`Generate bin grid — ${location.name}`}
        primaryButtonText={saving ? "Generating…" : "Generate"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !gridValid}
        onRequestClose={() => setGridOpen(false)}
        onRequestSubmit={() => void handleGenerate()}
      >
        <Stack gap={5}>
          <TextInput
            id={`grid-rows-${location.id}`}
            labelText="Rows"
            helperText="Comma list (A,B) or range (A–B). Codes look like A-01-1."
            value={gridRows}
            onChange={(event) => setGridRows(event.target.value)}
          />
          <NumberInput
            id={`grid-bays-${location.id}`}
            label="Bays"
            min={1}
            max={99}
            value={gridBays}
            onChange={(_event, { value }) => setGridBays(value === "" ? "" : Number(value))}
          />
          <NumberInput
            id={`grid-levels-${location.id}`}
            label="Levels"
            min={1}
            max={99}
            value={gridLevels}
            onChange={(_event, { value }) => setGridLevels(value === "" ? "" : Number(value))}
          />
          {gridValid ? (
            <p className="cds--type-body-01">
              Preview: {parsedRows[0]}-01-1 … {parsedRows[parsedRows.length - 1]}-
              {String(bayCount).padStart(2, "0")}-{levelCount} ({parsedRows.length * bayCount * levelCount}{" "}
              slots; existing bins are skipped).
            </p>
          ) : null}
        </Stack>
      </Modal>

      <Modal
        open={createOpen}
        modalHeading={`Add bin — ${location.name}`}
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id={`create-bin-row-${location.id}`}
            labelText="Row"
            value={createRow}
            onChange={(event) => setCreateRow(event.target.value)}
          />
          <NumberInput
            id={`create-bin-bay-${location.id}`}
            label="Bay"
            min={1}
            value={createBay}
            onChange={(_event, { value }) => setCreateBay(value === "" ? "" : Number(value))}
          />
          <NumberInput
            id={`create-bin-level-${location.id}`}
            label="Level"
            min={1}
            value={createLevel}
            onChange={(_event, { value }) => setCreateLevel(value === "" ? "" : Number(value))}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}
