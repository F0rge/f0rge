"use client";

import { Button, InlineNotification, Stack, TextInput } from "@carbon/react";
import { useEffect, useState } from "react";

import {
  ApiError,
  displayPrice,
  exVatToIncVat,
  formatPriceAmount,
  incVatToExVat,
  parsePriceInput,
  updateSku,
  type Sku,
  type UpdateSkuPricePayload,
} from "@/lib/api";

type PriceBasis = "ex" | "inc";

type PriceFormState = {
  wholesaleEx: string;
  wholesaleInc: string;
  retailEx: string;
  retailInc: string;
  lastEditedWholesale: PriceBasis | null;
  lastEditedRetail: PriceBasis | null;
};

type SkuPriceEditorProps = {
  sku: Sku | null;
  open: boolean;
  readOnly: boolean;
  unitCostZar: string | null;
  saving: boolean;
  onSavingChange: (saving: boolean) => void;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
};

const emptyForm: PriceFormState = {
  wholesaleEx: "",
  wholesaleInc: "",
  retailEx: "",
  retailInc: "",
  lastEditedWholesale: null,
  lastEditedRetail: null,
};

function formFromSku(sku: Sku): PriceFormState {
  return {
    wholesaleEx: sku.wholesale_ex_vat ?? "",
    wholesaleInc: sku.wholesale_inc_vat ?? "",
    retailEx: sku.retail_ex_vat ?? "",
    retailInc: sku.retail_inc_vat ?? "",
    lastEditedWholesale: null,
    lastEditedRetail: null,
  };
}

function buildPayload(form: PriceFormState): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = {};

  if (form.lastEditedWholesale === "ex") {
    payload.wholesale_ex_vat = form.wholesaleEx.trim() || null;
  } else if (form.lastEditedWholesale === "inc") {
    payload.wholesale_inc_vat = form.wholesaleInc.trim() || null;
  }

  if (form.lastEditedRetail === "ex") {
    payload.retail_ex_vat = form.retailEx.trim() || null;
  } else if (form.lastEditedRetail === "inc") {
    payload.retail_inc_vat = form.retailInc.trim() || null;
  }

  return payload;
}

export function SkuPriceEditor({
  sku,
  open,
  readOnly,
  unitCostZar,
  saving,
  onSavingChange,
  onClose,
  onSaved,
  onError,
}: SkuPriceEditorProps) {
  const [form, setForm] = useState<PriceFormState>(emptyForm);

  useEffect(() => {
    if (sku && open) {
      setForm(formFromSku(sku));
    }
    if (!open) {
      setForm(emptyForm);
    }
  }, [sku, open]);

  function updateWholesaleEx(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        wholesaleEx: value,
        wholesaleInc: parsed === null ? "" : formatPriceAmount(exVatToIncVat(parsed)),
        lastEditedWholesale: "ex",
      };
    });
  }

  function updateWholesaleInc(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        wholesaleInc: value,
        wholesaleEx: parsed === null ? "" : formatPriceAmount(incVatToExVat(parsed)),
        lastEditedWholesale: "inc",
      };
    });
  }

  function updateRetailEx(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        retailEx: value,
        retailInc: parsed === null ? "" : formatPriceAmount(exVatToIncVat(parsed)),
        lastEditedRetail: "ex",
      };
    });
  }

  function updateRetailInc(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        retailInc: value,
        retailEx: parsed === null ? "" : formatPriceAmount(incVatToExVat(parsed)),
        lastEditedRetail: "inc",
      };
    });
  }

  const hasEdits = form.lastEditedWholesale !== null || form.lastEditedRetail !== null;

  async function handleSave() {
    if (!sku || readOnly) {
      return;
    }
    const payload = buildPayload(form);
    if (Object.keys(payload).length === 0) {
      onClose();
      return;
    }

    onSavingChange(true);
    try {
      await updateSku(sku.id, payload);
      onClose();
      await onSaved();
    } catch (err) {
      if (err instanceof ApiError) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to save prices.");
      }
    } finally {
      onSavingChange(false);
    }
  }

  if (!open || !sku) {
    return null;
  }

  return (
    <section
      className="cds--layer-01"
      style={{
        padding: "1.5rem",
        border: "1px solid var(--cds-border-subtle-01, #e0e0e0)",
        maxWidth: "36rem",
      }}
      aria-labelledby="sku-price-editor-heading"
    >
      <Stack gap={5}>
        <div>
          <h2 id="sku-price-editor-heading" className="cds--type-productive-heading-03">
            {readOnly ? "SKU prices" : "Edit prices"}
          </h2>
          <p className="cds--type-body-01">
            <strong>{sku.our_ref}</strong> — {sku.name}
          </p>
        </div>
        {unitCostZar ? (
          <InlineNotification
            kind="info"
            title="Unit cost"
            subtitle={`Landed unit cost from inventory: ${displayPrice(unitCostZar)} ZAR`}
            hideCloseButton
            lowContrast
          />
        ) : null}
        <TextInput
          id="sku-wholesale-ex-vat"
          labelText="Wholesale ex-VAT"
          helperText="VAT 15% — paired inc-VAT updates as you type"
          value={form.wholesaleEx}
          readOnly={readOnly}
          onChange={(event) => updateWholesaleEx(event.target.value)}
        />
        <TextInput
          id="sku-wholesale-inc-vat"
          labelText="Wholesale inc-VAT"
          value={form.wholesaleInc}
          readOnly={readOnly}
          onChange={(event) => updateWholesaleInc(event.target.value)}
        />
        <TextInput
          id="sku-retail-ex-vat"
          labelText="Retail ex-VAT"
          helperText="VAT 15% — paired inc-VAT updates as you type"
          value={form.retailEx}
          readOnly={readOnly}
          onChange={(event) => updateRetailEx(event.target.value)}
        />
        <TextInput
          id="sku-retail-inc-vat"
          labelText="Retail inc-VAT"
          value={form.retailInc}
          readOnly={readOnly}
          onChange={(event) => updateRetailInc(event.target.value)}
        />
        <div style={{ display: "flex", gap: "0.75rem" }}>
          {readOnly ? (
            <Button type="button" kind="secondary" onClick={onClose}>
              Close
            </Button>
          ) : (
            <>
              <Button
                type="button"
                disabled={saving || !hasEdits}
                onClick={() => void handleSave()}
              >
                {saving ? "Saving…" : "Save"}
              </Button>
              <Button type="button" kind="secondary" disabled={saving} onClick={onClose}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </Stack>
    </section>
  );
}
