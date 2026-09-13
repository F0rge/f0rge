"use client";

import { Button, TextInput } from "@carbon/react";
import { Scan } from "@carbon/icons-react";
import { useState } from "react";

import { TillScanner } from "@/components/till-scanner";

type WmsScanFieldProps = {
  id: string;
  labelText: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value?: string) => void;
  disabled?: boolean;
  helperText?: string;
};

export function WmsScanField({
  id,
  labelText,
  placeholder = "Scan or type SKU / barcode",
  value,
  onChange,
  onSubmit,
  disabled = false,
  helperText,
}: WmsScanFieldProps) {
  const [scannerOpen, setScannerOpen] = useState(false);

  function applyCode(code: string) {
    onChange(code);
    setScannerOpen(false);
    onSubmit?.(code);
  }

  return (
    <>
      <div className="vellano-wms-scan-row vellano-wms-barcode">
        <TextInput
          id={id}
          labelText={labelText}
          helperText={helperText}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSubmit?.(value);
            }
          }}
        />
        <Button
          kind="secondary"
          size="lg"
          renderIcon={Scan}
          iconDescription="Open camera scanner"
          disabled={disabled}
          onClick={() => setScannerOpen(true)}
        >
          Scan
        </Button>
      </div>
      {scannerOpen ? (
        <TillScanner
          onClose={() => setScannerOpen(false)}
          onDetect={applyCode}
          onTypeIn={applyCode}
        />
      ) : null}
    </>
  );
}
