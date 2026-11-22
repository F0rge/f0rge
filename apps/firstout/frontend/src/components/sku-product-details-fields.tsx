"use client";

import { Column, Grid, Stack, TextArea, TextInput } from "@carbon/react";
import {
  SKU_DIMENSIONS,
  SKU_DIMENSION_FIELDS,
  SKU_NOTES_LIMIT,
  type SkuDetailsErrors,
  type SkuDetailsForm,
} from "@/lib/sku-details";

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
