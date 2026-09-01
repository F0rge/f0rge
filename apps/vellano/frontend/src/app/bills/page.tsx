"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
  Select,
  SelectItem,
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
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  canMutateBooks,
  createBill,
  formatZarAmount,
  listBills,
  listSuppliers,
  type Bill,
  type CreateBillLinePayload,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "bill_number", header: "Number" },
  { key: "supplier_name", header: "Supplier" },
  { key: "issue_date", header: "Issue date" },
  { key: "currency", header: "Currency" },
  { key: "amount_foreign", header: "Amount" },
  { key: "amount_zar", header: "ZAR" },
  { key: "balance_zar", header: "Balance ZAR" },
  { key: "actions", header: "" },
] as const;

type BillRow = {
  id: string;
  bill_number: string;
  supplier_name: string;
  issue_date: string;
  currency: string;
  amount_foreign: string;
  amount_zar: string;
  balance_zar: string;
  actions: string;
};

type BillLineForm = {
  description: string;
  qty: number | "";
  unit_amount: string;
};

const emptyLine = (): BillLineForm => ({
  description: "",
  qty: 1,
  unit_amount: "",
});

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function BillsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [bills, setBills] = useState<Bill[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [supplierRef, setSupplierRef] = useState("");
  const [issueDate, setIssueDate] = useState(todayIso());
  const [currency, setCurrency] = useState("USD");
  const [fxToZar, setFxToZar] = useState("");
  const [lines, setLines] = useState<BillLineForm[]>([emptyLine()]);

  const loadBills = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listBills();
      setBills(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bills.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const supplierData = await listSuppliers();
      setSuppliers(supplierData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suppliers.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadBills();
    }
  }, [user, loadBills]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  useEffect(() => {
    const supplier = suppliers.find((entry) => entry.id === supplierId);
    if (supplier) {
      setCurrency(supplier.default_currency || "USD");
    }
  }, [supplierId, suppliers]);

  const linesValid = lines.every(
    (line) =>
      line.description.trim() &&
      typeof line.qty === "number" &&
      line.qty > 0 &&
      line.unit_amount.trim(),
  );
  const fxRequired = currency !== "ZAR";
  const formValid =
    supplierId &&
    supplierRef.trim() &&
    issueDate &&
    lines.length >= 1 &&
    linesValid &&
    (!fxRequired || fxToZar.trim());

  function resetCreateForm() {
    setSupplierId("");
    setSupplierRef("");
    setIssueDate(todayIso());
    setCurrency("USD");
    setFxToZar("");
    setLines([emptyLine()]);
  }

  function updateLine(index: number, patch: Partial<BillLineForm>) {
    setLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, ...patch } : line)),
    );
  }

  function addLine() {
    setLines((current) => [...current, emptyLine()]);
  }

  function removeLine(index: number) {
    setLines((current) => (current.length > 1 ? current.filter((_, i) => i !== index) : current));
  }

  async function handleCreate() {
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        supplier_id: supplierId,
        supplier_ref: supplierRef.trim(),
        issue_date: issueDate,
        currency: currency.trim(),
        fx_to_zar: fxRequired ? fxToZar.trim() : undefined,
        lines: lines.map(
          (line): CreateBillLinePayload => ({
            description: line.description.trim(),
            qty: line.qty as number,
            unit_amount: line.unit_amount.trim(),
          }),
        ),
      };
      const created = await createBill(payload);
      setCreateOpen(false);
      resetCreateForm();
      router.push(`/bills/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create bill.");
    } finally {
      setSaving(false);
    }
  }

  const rows: BillRow[] = bills.map((entry) => ({
    id: entry.id,
    bill_number: entry.bill_number,
    supplier_name: entry.supplier_name,
    issue_date: entry.issue_date,
    currency: entry.currency,
    amount_foreign: `${entry.currency} ${entry.amount_foreign}`,
    amount_zar: formatZarAmount(entry.amount_zar),
    balance_zar: formatZarAmount(entry.balance_zar),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Bills</h1>
          <p className="cds--type-body-01">Supplier bills in foreign currency with ZAR conversion.</p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            Create bill
          </Button>
        ) : null}
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

      {loading ? (
        <p className="cds--type-body-01">Loading bills…</p>
      ) : bills.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No bills"
          subtitle="No supplier bills have been recorded yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Bills" description="All Vellano supplier bills">
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })} key={header.key}>
                        {header.header}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.map((row) => (
                    <TableRow
                      {...getRowProps({ row })}
                      key={row.id}
                      onClick={() => router.push(`/bills/${row.id}`)}
                      style={{ cursor: "pointer" }}
                    >
                      {row.cells.map((cell) => {
                        if (cell.info.header === "actions") {
                          return (
                            <TableCell key={cell.id}>
                              <Button
                                kind="ghost"
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  router.push(`/bills/${row.id}`);
                                }}
                              >
                                Open
                              </Button>
                            </TableCell>
                          );
                        }
                        return <TableCell key={cell.id}>{cell.value}</TableCell>;
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      <Modal
        open={createOpen}
        modalHeading="Create bill"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <Select
            id="bill-supplier"
            labelText="Supplier"
            value={supplierId}
            onChange={(event) => setSupplierId(event.target.value)}
          >
            <SelectItem value="" text="Select a supplier" />
            {suppliers.map((supplier) => (
              <SelectItem key={supplier.id} value={supplier.id} text={supplier.name} />
            ))}
          </Select>
          <TextInput
            id="bill-supplier-ref"
            labelText="Supplier reference"
            value={supplierRef}
            onChange={(event) => setSupplierRef(event.target.value)}
            required
          />
          <TextInput
            id="bill-issue-date"
            labelText="Issue date"
            type="date"
            value={issueDate}
            onChange={(event) => setIssueDate(event.target.value)}
            required
          />
          <TextInput
            id="bill-currency"
            labelText="Currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            required
          />
          {currency !== "ZAR" ? (
            <TextInput
              id="bill-fx"
              labelText="FX to ZAR"
              helperText="ZAR per 1 unit of foreign currency"
              value={fxToZar}
              onChange={(event) => setFxToZar(event.target.value)}
              required
            />
          ) : null}
          <div>
            <p className="cds--label">Lines</p>
            <Stack gap={4}>
              {lines.map((line, index) => (
                <div
                  key={`line-${index}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1fr 1fr auto",
                    gap: "0.5rem",
                    alignItems: "end",
                  }}
                >
                  <TextInput
                    id={`bill-line-desc-${index}`}
                    labelText={index === 0 ? "Description" : ""}
                    hideLabel={index > 0}
                    value={line.description}
                    onChange={(event) => updateLine(index, { description: event.target.value })}
                  />
                  <NumberInput
                    id={`bill-line-qty-${index}`}
                    label={index === 0 ? "Qty" : ""}
                    hideLabel={index > 0}
                    min={1}
                    value={line.qty}
                    onChange={(_, { value }) =>
                      updateLine(index, { qty: value === "" ? "" : Number(value) })
                    }
                  />
                  <TextInput
                    id={`bill-line-unit-${index}`}
                    labelText={index === 0 ? "Unit amount" : ""}
                    hideLabel={index > 0}
                    value={line.unit_amount}
                    onChange={(event) => updateLine(index, { unit_amount: event.target.value })}
                  />
                  {lines.length > 1 ? (
                    <Button kind="ghost" size="sm" onClick={() => removeLine(index)}>
                      Remove
                    </Button>
                  ) : (
                    <span />
                  )}
                </div>
              ))}
            </Stack>
            <Button kind="ghost" size="sm" onClick={addLine} style={{ marginTop: "0.5rem" }}>
              Add line
            </Button>
          </div>
        </Stack>
      </Modal>
    </Stack>
  );
}
