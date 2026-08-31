"use client";

import {
  Button,
  DataTable,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
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
import { useCallback, useEffect, useState } from "react";

import {
  canMutateCatalogue,
  createProforma,
  listProformas,
  listSuppliers,
  type Proforma,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "supplier_name", header: "Supplier" },
  { key: "invoice_number", header: "Invoice number" },
  { key: "invoice_date", header: "Date" },
  { key: "currency", header: "Currency" },
  { key: "pdf", header: "PDF" },
] as const;

type ProformaRow = {
  id: string;
  supplier_name: string;
  invoice_number: string;
  invoice_date: string;
  currency: string;
  pdf: string;
};

type ProformaForm = {
  supplier_id: string;
  invoice_number: string;
  invoice_date: string;
  currency: string;
};

const emptyForm: ProformaForm = {
  supplier_id: "",
  invoice_number: "",
  invoice_date: "",
  currency: "",
};

export default function ProformasPage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user?.role);
  const [proformas, setProformas] = useState<Proforma[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<ProformaForm>(emptyForm);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  const loadProformas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listProformas();
      setProformas(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load proformas.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadSuppliers = useCallback(async () => {
    try {
      const data = await listSuppliers();
      setSuppliers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suppliers.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadProformas();
    }
  }, [user, loadProformas]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadSuppliers();
    }
  }, [createOpen, canMutate, loadSuppliers]);

  const rows: ProformaRow[] = proformas.map((entry) => ({
    id: entry.id,
    supplier_name: entry.supplier_name,
    invoice_number: entry.invoice_number,
    invoice_date: entry.invoice_date,
    currency: entry.currency,
    pdf: entry.id,
  }));

  function resetForm() {
    setForm(emptyForm);
    setPdfFile(null);
  }

  function openCreate() {
    resetForm();
    setCreateOpen(true);
  }

  async function handleCreate() {
    if (!pdfFile) {
      setError("A PDF file is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createProforma({
        supplier_id: form.supplier_id,
        invoice_number: form.invoice_number.trim(),
        invoice_date: form.invoice_date,
        currency: form.currency.trim() || undefined,
        file: pdfFile,
      });
      setCreateOpen(false);
      resetForm();
      await loadProformas();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to file performing invoice.");
    } finally {
      setSaving(false);
    }
  }

  const formValid =
    form.supplier_id && form.invoice_number.trim() && form.invoice_date && pdfFile;

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Proformas</h1>
          <p className="cds--type-body-01">Performing invoices filed against suppliers.</p>
        </div>
        {canMutate ? (
          <Button onClick={openCreate}>File performing invoice</Button>
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
        <p className="cds--type-body-01">Loading proformas…</p>
      ) : proformas.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No proformas"
          subtitle="No performing invoices have been filed yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Proformas" description="All filed performing invoices">
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
                    <TableRow {...getRowProps({ row })} key={row.id}>
                      {row.cells.map((cell) => {
                        if (cell.info.header === "pdf") {
                          return (
                            <TableCell key={cell.id}>
                              <Button
                                kind="ghost"
                                size="sm"
                                href={`/api/v1/proformas/${row.id}/file`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Open PDF
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
        modalHeading="File performing invoice"
        primaryButtonText={saving ? "Filing…" : "File"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <Select
            id="proforma-supplier"
            labelText="Supplier"
            value={form.supplier_id}
            onChange={(event) =>
              setForm((current) => ({ ...current, supplier_id: event.target.value }))
            }
          >
            <SelectItem value="" text="Select a supplier" />
            {suppliers.map((supplier) => (
              <SelectItem key={supplier.id} value={supplier.id} text={supplier.name} />
            ))}
          </Select>
          <TextInput
            id="proforma-invoice-number"
            labelText="Invoice number"
            value={form.invoice_number}
            onChange={(event) =>
              setForm((current) => ({ ...current, invoice_number: event.target.value }))
            }
            required
          />
          <TextInput
            id="proforma-invoice-date"
            labelText="Invoice date"
            type="date"
            value={form.invoice_date}
            onChange={(event) =>
              setForm((current) => ({ ...current, invoice_date: event.target.value }))
            }
            required
          />
          <TextInput
            id="proforma-currency"
            labelText="Currency"
            helperText="Defaults to USD"
            value={form.currency}
            onChange={(event) =>
              setForm((current) => ({ ...current, currency: event.target.value }))
            }
          />
          <div>
            <p className="cds--label">PDF</p>
            <FileUploaderDropContainer
              accept={["application/pdf", ".pdf"]}
              labelText="Drag and drop a PDF here or click to upload"
              multiple={false}
              onAddFiles={(_, { addedFiles }) => {
                const file = addedFiles[0];
                if (file && !file.invalidFileType) {
                  setPdfFile(file);
                }
              }}
            />
            {pdfFile ? (
              <FileUploaderItem
                name={pdfFile.name}
                status="complete"
                onDelete={() => setPdfFile(null)}
              />
            ) : null}
          </div>
        </Stack>
      </Modal>
    </Stack>
  );
}
