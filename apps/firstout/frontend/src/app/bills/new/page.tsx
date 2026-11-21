"use client";

import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { PageLoading } from "@/components/page-loading";
import {
  canMutateBooks,
  createBill,
  getBill,
  listSuppliers,
  uploadBillAttachment,
  type BillApprovalStatus,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localIsoDate } from "@/lib/till-statement";

type LineForm = { description: string; qty: number | ""; unit_amount: string };

const emptyLine = (): LineForm => ({ description: "", qty: 1, unit_amount: "" });

function addDays(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  return localIsoDate(new Date(year, month - 1, day + days));
}

export default function NewBillPage() {
  return (
    <Suspense fallback={<PageLoading label="Loading bill form…" kind="status" />}>
      <NewBill />
    </Suspense>
  );
}

function NewBill() {
  const router = useRouter();
  const duplicateOf = useSearchParams().get("from");
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [supplierRef, setSupplierRef] = useState("");
  const [issueDate, setIssueDate] = useState(localIsoDate());
  const [dueDate, setDueDate] = useState(addDays(localIsoDate(), 30));
  const [dueTouched, setDueTouched] = useState(false);
  const [currency, setCurrency] = useState("ZAR");
  const [fxToZar, setFxToZar] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<LineForm[]>([emptyLine()]);
  const [files, setFiles] = useState<File[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([listSuppliers(), duplicateOf ? getBill(duplicateOf) : Promise.resolve(null)])
      .then(([supplierList, source]) => {
        if (cancelled) return;
        setSuppliers(supplierList);
        if (!source) return;
        // A duplicate copies the supplier and lines; the reference and dates are new.
        setSupplierId(source.supplier_id);
        setCurrency(source.currency);
        setFxToZar(source.currency === "ZAR" ? "" : source.fx_to_zar);
        setNotes(source.notes ?? "");
        setLines(
          source.lines.map((line) => ({
            description: line.description,
            qty: Number(line.qty),
            unit_amount: line.unit_amount,
          })),
        );
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load suppliers.");
      });
    return () => {
      cancelled = true;
    };
  }, [user, duplicateOf]);

  const foreign = currency.trim().toUpperCase() !== "ZAR";
  const linesValid = lines.every(
    (line) => line.description.trim() && typeof line.qty === "number" && line.qty > 0 && Number(line.unit_amount) > 0,
  );
  const dueValid = !dueDate || dueDate >= issueDate;
  const formValid =
    !!supplierId && !!supplierRef.trim() && !!issueDate && dueValid && linesValid && (!foreign || Number(fxToZar) > 0);

  function chooseSupplier(id: string) {
    setSupplierId(id);
    const supplier = suppliers.find((entry) => entry.id === id);
    if (supplier) setCurrency(supplier.default_currency || "ZAR");
  }

  function updateLine(index: number, patch: Partial<LineForm>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  async function save(approval: BillApprovalStatus) {
    if (!formValid) return;
    setSaving(true);
    setError(null);
    try {
      const bill = await createBill({
        supplier_id: supplierId,
        supplier_ref: supplierRef.trim(),
        issue_date: issueDate,
        due_date: dueDate || undefined,
        currency: currency.trim(),
        fx_to_zar: foreign ? fxToZar.trim() : undefined,
        notes: notes.trim() || undefined,
        approval_status: approval,
        lines: lines.map((line) => ({
          description: line.description.trim(),
          qty: Number(line.qty),
          unit_amount: line.unit_amount.trim(),
        })),
      });
      const failed: string[] = [];
      for (const file of files) {
        try {
          await uploadBillAttachment(bill.id, file);
        } catch {
          failed.push(file.name);
        }
      }
      if (failed.length) {
        setSavedId(bill.id);
        setError(`${bill.bill_number} was saved, but these files did not upload: ${failed.join(", ")}. Add them from the bill.`);
        return;
      }
      router.push(`/bills/${bill.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save bill.");
    } finally {
      setSaving(false);
    }
  }

  if (user && !canMutate) {
    return (
      <InlineNotification
        kind="error"
        title="Not allowed"
        subtitle="Creating a bill needs books access."
        hideCloseButton
        lowContrast
      />
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Create bill</h1>
        <p className="cds--type-body-01">Enter a supplier invoice. Approve it when it&apos;s ready to pay.</p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title={savedId ? "Some files did not upload" : "Could not save"}
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      <Stack gap={5}>
        <p className="cds--type-productive-heading-02">Supplier and dates</p>
        <Select id="bill-supplier" labelText="Supplier" value={supplierId} onChange={(event) => chooseSupplier(event.target.value)}>
          <SelectItem value="" text="Select a supplier" />
          {suppliers.map((supplier) => (
            <SelectItem key={supplier.id} value={supplier.id} text={supplier.name} />
          ))}
        </Select>
        <TextInput
          id="bill-supplier-ref"
          labelText="Supplier invoice reference"
          helperText="The number printed on their invoice."
          value={supplierRef}
          onChange={(event) => setSupplierRef(event.target.value)}
        />
        <TextInput
          id="bill-issue-date"
          labelText="Issue date"
          type="date"
          value={issueDate}
          onChange={(event) => {
            setIssueDate(event.target.value);
            if (!dueTouched && event.target.value) setDueDate(addDays(event.target.value, 30));
          }}
        />
        <TextInput
          id="bill-due-date"
          labelText="Due date"
          type="date"
          helperText="Defaults to 30 days after the issue date."
          value={dueDate}
          invalid={!dueValid}
          invalidText="The due date can't be before the issue date."
          onChange={(event) => {
            setDueDate(event.target.value);
            setDueTouched(true);
          }}
        />
        <TextInput id="bill-currency" labelText="Currency" value={currency} onChange={(event) => setCurrency(event.target.value)} />
        {foreign ? (
          <TextInput
            id="bill-fx"
            labelText={`FX rate, ${currency.trim().toUpperCase()} to ZAR`}
            helperText="Use the rate on the issue date."
            value={fxToZar}
            onChange={(event) => setFxToZar(event.target.value)}
          />
        ) : null}
      </Stack>

      <Stack gap={4}>
        <p className="cds--type-productive-heading-02">Lines</p>
        {lines.map((line, index) => (
          <div
            key={`line-${index}`}
            style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr auto", gap: "0.5rem", alignItems: "end" }}
          >
            <TextInput
              id={`bill-line-desc-${index}`}
              labelText="Description"
              hideLabel={index > 0}
              value={line.description}
              onChange={(event) => updateLine(index, { description: event.target.value })}
            />
            <NumberInput
              id={`bill-line-qty-${index}`}
              label="Qty"
              hideLabel={index > 0}
              min={1}
              value={line.qty}
              onChange={(_, { value }) => updateLine(index, { qty: value === "" ? "" : Number(value) })}
            />
            <TextInput
              id={`bill-line-unit-${index}`}
              labelText="Unit amount"
              hideLabel={index > 0}
              value={line.unit_amount}
              onChange={(event) => updateLine(index, { unit_amount: event.target.value })}
            />
            <Button
              kind="ghost"
              size="sm"
              disabled={lines.length === 1}
              onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
            >
              Remove
            </Button>
          </div>
        ))}
        <div>
          <Button kind="ghost" size="sm" onClick={() => setLines((current) => [...current, emptyLine()])}>
            Add line
          </Button>
        </div>
      </Stack>

      <Stack gap={4}>
        <p className="cds--type-productive-heading-02">Attachments</p>
        <FileUploaderDropContainer
          accept={["application/pdf", ".pdf", "image/png", ".png", "image/jpeg", ".jpg", ".jpeg"]}
          labelText="Drag a PDF or image here, or click to choose. Add as many as you need."
          multiple
          onAddFiles={(_, { addedFiles }) =>
            setFiles((current) => [...current, ...addedFiles.filter((file) => !file.invalidFileType)])
          }
        />
        {files.map((file, index) => (
          <FileUploaderItem
            key={`${file.name}-${index}`}
            name={file.name}
            status="edit"
            onDelete={() => setFiles((current) => current.filter((_, i) => i !== index))}
          />
        ))}
      </Stack>

      <TextArea
        id="bill-notes"
        labelText="Notes"
        helperText="Staff only."
        rows={3}
        maxLength={4000}
        value={notes}
        onChange={(event) => setNotes(event.target.value)}
      />

      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", justifyContent: "flex-end" }}>
        {savedId ? (
          <Button href={`/bills/${savedId}`}>Open bill</Button>
        ) : (
          <>
            <Button kind="ghost" href="/bills">
              Cancel
            </Button>
            <Button kind="secondary" disabled={saving || !formValid} onClick={() => void save("draft")}>
              Save draft
            </Button>
            <Button disabled={saving || !formValid} onClick={() => void save("approved")}>
              {saving ? "Saving…" : "Save and approve"}
            </Button>
          </>
        )}
      </div>
    </Stack>
  );
}
