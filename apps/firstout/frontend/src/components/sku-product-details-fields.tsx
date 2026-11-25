"use client";

import { Button, Column, Grid, Stack, TextArea, TextInput } from "@carbon/react";
import {
  SKU_DIMENSIONS,
  SKU_DIMENSION_FIELDS,
  SKU_NOTES_LIMIT,
  SKU_SWATCH_PATTERN,
  type SkuDetailsErrors,
  type SkuDetailsForm,
} from "@/lib/sku-details";

import styles from "./sku-product-details-fields.module.css";

export function SkuProductDetailsFields({
  idPrefix, form, errors, readOnly, disabled, onChange,
}: {
  idPrefix: string;
  form: SkuDetailsForm;
  errors: SkuDetailsErrors;
  readOnly?: boolean;
  disabled?: boolean;
  onChange: (field: keyof SkuDetailsForm, value: string) => void;
}) {
  return (
    <Stack gap={5}>
      <Grid condensed fullWidth>
        {SKU_DIMENSIONS.map((field) => (
          <Column key={field} sm={4} md={4} lg={8}>
          <TextInput
            id={`${idPrefix}-${field}`}
            inputMode="decimal"
            labelText={SKU_DIMENSION_FIELDS[field]}
            value={form[field]}
            invalid={Boolean(errors[field])}
            invalidText={errors[field]}
            readOnly={readOnly}
            disabled={disabled}
            onChange={(event) => onChange(field, event.target.value)}
          />
          </Column>
        ))}
        <Column sm={4} md={4} lg={8}>
        <TextInput
          id={`${idPrefix}-piece_count`}
          inputMode="numeric"
          labelText="Pieces per sellable unit"
          helperText="Count the pieces that make up this SKU. Cartons and kit components have their own fields."
          value={form.piece_count}
          invalid={Boolean(errors.piece_count)}
          invalidText={errors.piece_count}
          readOnly={readOnly}
          disabled={disabled}
          onChange={(event) => onChange("piece_count", event.target.value)}
        />
        </Column>
        <Column sm={4} md={8} lg={16}>
        <div className={styles.swatch}>
          <TextInput
            id={`${idPrefix}-swatch_hex`}
            labelText="Swatch colour"
            helperText="The finish dot on the DasKasas shop, as # and six hex digits. Leave blank for none."
            placeholder="#9b9592"
            maxLength={7}
            value={form.swatch_hex}
            invalid={Boolean(errors.swatch_hex)}
            invalidText={errors.swatch_hex}
            readOnly={readOnly}
            disabled={disabled}
            onChange={(event) => onChange("swatch_hex", event.target.value)}
          />
          <input
            type="color"
            aria-label="Pick swatch colour"
            value={SKU_SWATCH_PATTERN.test(form.swatch_hex.trim().toLowerCase()) ? form.swatch_hex.trim().toLowerCase() : "#ffffff"}
            disabled={readOnly || disabled}
            onChange={(event) => onChange("swatch_hex", event.target.value)}
            className={styles.picker}
          />
          {!readOnly && (
            <Button
              kind="ghost"
              size="md"
              className={styles.clear}
              disabled={disabled || !form.swatch_hex}
              onClick={() => onChange("swatch_hex", "")}
            >
              Clear
            </Button>
          )}
        </div>
        </Column>
      </Grid>
      <TextArea
        id={`${idPrefix}-notes`}
        labelText="Internal notes"
        helperText="Visible to Firstout staff."
        maxLength={SKU_NOTES_LIMIT}
        rows={3}
        value={form.notes}
        invalid={Boolean(errors.notes)}
        invalidText={errors.notes}
        readOnly={readOnly}
        disabled={disabled}
        onChange={(event) => onChange("notes", event.target.value)}
      />
    </Stack>
  );
}
