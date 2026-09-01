"use client";

import {
  Button,
  DatePicker,
  DatePickerInput,
  InlineNotification,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  downloadVat201Csv,
  downloadVat201Pdf,
  formatZarAmount,
  getVat201Draft,
  type Vat201Draft,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function monthStartIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function Vat201Page() {
  const { user } = useAuth();
  const [fromDate, setFromDate] = useState(monthStartIso());
  const [toDate, setToDate] = useState(todayIso());
  const [draft, setDraft] = useState<Vat201Draft | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolvePeriod = useCallback(() => {
    const effectiveFrom = fromDate.trim() || monthStartIso();
    const effectiveTo = toDate.trim() || todayIso();

    if (!fromDate.trim()) setFromDate(effectiveFrom);
    if (!toDate.trim()) setToDate(effectiveTo);

    return { effectiveFrom, effectiveTo };
  }, [fromDate, toDate]);

  const loadDraft = useCallback(async () => {
    const { effectiveFrom, effectiveTo } = resolvePeriod();

    setLoading(true);
    setError(null);
    try {
      const result = await getVat201Draft(effectiveFrom, effectiveTo);
      setDraft(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load VAT201 draft.");
    } finally {
      setLoading(false);
    }
  }, [resolvePeriod]);

  const handleDownloadCsv = useCallback(async () => {
    const { effectiveFrom, effectiveTo } = resolvePeriod();
    try {
      await downloadVat201Csv(effectiveFrom, effectiveTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }, [resolvePeriod]);

  const handleDownloadPdf = useCallback(async () => {
    const { effectiveFrom, effectiveTo } = resolvePeriod();
    try {
      await downloadVat201Pdf(effectiveFrom, effectiveTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download PDF.");
    }
  }, [resolvePeriod]);

  useEffect(() => {
    if (user) {
      void loadDraft();
    }
  }, [user, loadDraft]);

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">VAT201 draft</h1>
        <p className="cds--type-body-01">
          Shaped fields for manual entry into SARS eFiling. This app never files VAT or contacts
          SARS.
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      <InlineNotification
        kind="warning"
        title="Draft only"
        subtitle="Copy these values into eFiling manually. No submission to SARS occurs from this application."
        hideCloseButton
        lowContrast
      />

      <Stack gap={4} orientation="horizontal">
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={fromDate}>
          <DatePickerInput
            id="vat-from"
            labelText="Period from"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setFromDate(event.target.value)}
          />
        </DatePicker>
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={toDate}>
          <DatePickerInput
            id="vat-to"
            labelText="Period to"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setToDate(event.target.value)}
          />
        </DatePicker>
        <Button kind="primary" disabled={loading} onClick={() => void loadDraft()}>
          {loading ? "Loading…" : "Load draft"}
        </Button>
      </Stack>

      {draft ? (
        <Stack gap={6}>
          <Stack gap={4} orientation="horizontal">
            <TextInput
              id="vendor-name"
              labelText="Vendor name"
              value={draft.vendor_name}
              readOnly
            />
            <TextInput
              id="vendor-vat"
              labelText="VAT number"
              value={draft.vendor_vat_number}
              readOnly
            />
          </Stack>

          <TableContainer
            title="VAT201 fields"
            description="Copy into eFiling — Field numbers match common VAT201 layout"
          >
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Field</TableHeader>
                  <TableHeader>Description</TableHeader>
                  <TableHeader>Amount (ZAR)</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>1</TableCell>
                  <TableCell>Standard rated supplies (excl VAT)</TableCell>
                  <TableCell>
                    <TextInput
                      id="field-1"
                      labelText=""
                      hideLabel
                      value={draft.standard_rated_supplies_ex_vat}
                      readOnly
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>2</TableCell>
                  <TableCell>Output tax at 15%</TableCell>
                  <TableCell>
                    <TextInput
                      id="field-2"
                      labelText=""
                      hideLabel
                      value={draft.output_tax}
                      readOnly
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>3</TableCell>
                  <TableCell>Input tax</TableCell>
                  <TableCell>
                    <TextInput
                      id="field-3"
                      labelText=""
                      hideLabel
                      value={draft.input_tax}
                      readOnly
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>4</TableCell>
                  <TableCell>Net VAT payable</TableCell>
                  <TableCell>
                    <TextInput
                      id="field-4"
                      labelText=""
                      hideLabel
                      value={draft.net_vat_payable}
                      readOnly
                    />
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>

          <p className="cds--type-body-01">
            Period: {draft.period_from} to {draft.period_to} — {draft.invoice_count} invoice(s),{" "}
            {draft.credit_note_count} credit note(s). Net payable:{" "}
            {formatZarAmount(draft.net_vat_payable)}
          </p>

          <Stack gap={4} orientation="horizontal">
            <Button kind="secondary" onClick={() => void handleDownloadCsv()}>
              Download CSV
            </Button>
            <Button kind="tertiary" onClick={() => void handleDownloadPdf()}>
              Download PDF
            </Button>
          </Stack>
        </Stack>
      ) : null}
    </Stack>
  );
}
