"use client";

import { Select, SelectItem, Stack, TextInput } from "@carbon/react";

import type { LocationBin } from "@/lib/api";
import { matchBinByCode } from "@/lib/bin-helpers";

type BinSelectProps = {
  id: string;
  labelText: string;
  value: string;
  bins: LocationBin[];
  onChange: (binId: string) => void;
  disabled?: boolean;
  helperText?: string;
};

export function BinSelect({
  id,
  labelText,
  value,
  bins,
  onChange,
  disabled,
  helperText,
}: BinSelectProps) {
  return (
    <Select
      id={id}
      labelText={labelText}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      helperText={helperText}
    >
      <SelectItem value="" text="Default bin" />
      {bins.map((bin) => (
        <SelectItem
          key={bin.id}
          value={bin.id}
          text={bin.is_default ? `${bin.code} (default)` : bin.code}
        />
      ))}
    </Select>
  );
}

type BinScanFieldProps = {
  id: string;
  bins: LocationBin[];
  onMatch: (binId: string) => void;
  disabled?: boolean;
};

export function BinScanField({ id, bins, onMatch, disabled }: BinScanFieldProps) {
  return (
    <TextInput
      id={id}
      labelText="Bin code"
      placeholder="Type or scan bin code"
      disabled={disabled}
      onChange={(event) => {
        const match = matchBinByCode(bins, event.target.value);
        if (match) {
          onMatch(match.id);
        }
      }}
    />
  );
}

type LocationBinFieldsProps = {
  idPrefix: string;
  locationId: string;
  bins: LocationBin[];
  value: string;
  onChange: (binId: string) => void;
  includeScan?: boolean;
};

export function LocationBinFields({
  idPrefix,
  locationId,
  bins,
  value,
  onChange,
  includeScan = false,
}: LocationBinFieldsProps) {
  if (!locationId) {
    return null;
  }
  return (
    <Stack gap={5}>
      <BinSelect
        id={`${idPrefix}-bin`}
        labelText="Bin"
        value={value}
        bins={bins}
        onChange={onChange}
        helperText="Optional. Default FLOOR bin is used when left as default."
      />
      {includeScan ? (
        <BinScanField
          key={locationId}
          id={`${idPrefix}-bin-scan`}
          bins={bins}
          onMatch={onChange}
        />
      ) : null}
    </Stack>
  );
}
