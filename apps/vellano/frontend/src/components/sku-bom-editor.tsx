"use client";

import {
  Button,
  ComboBox,
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
} from "@carbon/react";
import { Add, TrashCan } from "@carbon/icons-react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  listSkuBom,
  replaceSkuBom,
  type Sku,
  type SkuBomLineWrite,
} from "@/lib/api";

type SkuBomEditorProps = {
  sku: Sku | null;
  skus: Sku[];
  open: boolean;
  canMutate: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
};

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

function componentLabel(skus: Sku[], id: string): string {
  const sku = skus.find((entry) => entry.id === id);
  return sku ? `${sku.our_ref} — ${sku.name}` : id;
}

export function SkuBomEditor({
  sku,
  skus,
  open,
  canMutate,
  onClose,
  onSaved,
  onError,
}: SkuBomEditorProps) {
  const [lines, setLines] = useState<SkuBomLineWrite[]>([]);
  const [selectedSku, setSelectedSku] = useState<Sku | null>(null);
  const [qty, setQty] = useState<number | "">(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !sku) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    setSelectedSku(null);
    setQty(1);
    listSkuBom(sku.id)
      .then((rows) => {
        if (!cancelled) {
          setLines(
            rows
              .filter((row) => row.component_sku_id !== sku.id)
              .map((row) => ({ component_sku_id: row.component_sku_id, qty: row.qty })),
          );
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLines([]);
          setLoadError(err instanceof Error ? err.message : "Failed to load kit components.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, sku]);

  const usedIds = useMemo(() => new Set(lines.map((line) => line.component_sku_id)), [lines]);
  const skuOptions = useMemo(
    () => skus.filter((entry) => entry.id !== sku?.id && !usedIds.has(entry.id)),
    [skus, sku?.id, usedIds],
  );
  const qtyValid = typeof qty === "number" && Number.isInteger(qty) && qty >= 1;
  const linesValid = lines.every(
    (line) =>
      line.component_sku_id !== sku?.id && Number.isInteger(line.qty) && line.qty >= 1,
  );

  function addLine() {
    if (!selectedSku || !qtyValid || selectedSku.id === sku?.id) {
      return;
    }
    setLines((prev) => [...prev, { component_sku_id: selectedSku.id, qty }]);
    setSelectedSku(null);
    setQty(1);
  }

  async function handleSave() {
    if (!sku || !canMutate || !linesValid) {
      return;
    }
    setSaving(true);
    try {
      await replaceSkuBom(sku.id, { lines });
      await onSaved();
      onClose();
    } catch (err) {
      if (err instanceof ApiError) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to save kit components.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open && sku !== null}
      modalHeading={sku ? `Kit components — ${sku.our_ref}` : "Kit components"}
      passiveModal={!canMutate}
      primaryButtonText={saving ? "Saving…" : "Save"}
      secondaryButtonText="Cancel"
      onRequestClose={onClose}
      onRequestSubmit={() => void handleSave()}
      primaryButtonDisabled={saving || loading || !linesValid}
      size="md"
    >
      <Stack gap={5}>
        <p className="cds--type-body-01">
          Virtual kit: stock and till consume these components. Sofa cartons belong on Cartons,
          not here.
        </p>
        {loadError ? (
          <InlineNotification
            kind="error"
            title="Error"
            subtitle={loadError}
            hideCloseButton
            lowContrast
          />
        ) : null}
        {loading ? <p className="cds--type-body-01">Loading components…</p> : null}
        {canMutate ? (
          <Stack gap={4}>
            <ComboBox
              id="kit-bom-sku"
              titleText="Component SKU"
              placeholder="Search catalogue…"
              items={skuOptions}
              itemToString={skuItemToString}
              shouldFilterItem={shouldFilterSku}
              selectedItem={selectedSku}
              onChange={({ selectedItem }) => setSelectedSku(selectedItem ?? null)}
              helperText="Parent SKU is excluded."
              disabled={loading || saving}
            />
            <NumberInput
              id="kit-bom-qty"
              label="Qty"
              min={1}
              step={1}
              allowEmpty
              value={qty}
              invalid={qty !== "" && !qtyValid}
              invalidText="Qty must be 1 or more"
              onChange={(_event, { value }) => {
                setQty(value === "" ? "" : Number(value));
              }}
              disabled={loading || saving}
            />
            <Button
              kind="secondary"
              size="sm"
              renderIcon={Add}
              disabled={loading || saving || !selectedSku || !qtyValid}
              onClick={addLine}
            >
              Add component
            </Button>
          </Stack>
        ) : null}
        {lines.length === 0 && !loading ? (
          <p className="cds--type-body-01">No kit components.</p>
        ) : (
          <Table size="sm">
            <TableHead>
              <TableRow>
                <TableHeader>Component</TableHeader>
                <TableHeader>Qty</TableHeader>
                {canMutate ? <TableHeader> </TableHeader> : null}
              </TableRow>
            </TableHead>
            <TableBody>
              {lines.map((line) => (
                <TableRow key={line.component_sku_id}>
                  <TableCell>{componentLabel(skus, line.component_sku_id)}</TableCell>
                  <TableCell>{line.qty}</TableCell>
                  {canMutate ? (
                    <TableCell>
                      <Button
                        kind="ghost"
                        size="sm"
                        hasIconOnly
                        iconDescription="Remove"
                        renderIcon={TrashCan}
                        disabled={saving}
                        onClick={() =>
                          setLines((prev) =>
                            prev.filter((entry) => entry.component_sku_id !== line.component_sku_id),
                          )
                        }
                      />
                    </TableCell>
                  ) : null}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Stack>
    </Modal>
  );
}
