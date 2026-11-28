"use client";

import { ErrorNotice } from "@/components/error-notice";
import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
  Modal,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  canMutateCatalogue,
  createProforma,
  downloadProformaPdf,
  listSuppliers,
  type Proforma,
} from "@/lib/api";
import { usePageError } from "@/hooks/use-page-error";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import { RecordWorkspace, RecordDetails, RecordDetail, type RecordWorkspaceAdapter } from "@/components/record-workspace";

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
  return <ProformasContent key={workspaceIdentity(user)} />;
}

function ProformasContent() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [refreshKey, setRefreshKey] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const suppliersQuery = useQuery({ queryKey: ["suppliers"], queryFn: () => listSuppliers(), enabled: createOpen && canMutate });
  const suppliers = suppliersQuery.data ?? [];
  const { error, setError } = usePageError(suppliersQuery.error, "Failed to load suppliers.");
  const [form, setForm] = useState<ProformaForm>(emptyForm);
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);

  function resetForm() {
    setForm(emptyForm);
    setPdfFile(null);
  }

  function openCreate() {

    setError(null);
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
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to file proforma invoice.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload(proformaId: string, invoiceNumber: string) {
    setError(null);
    try {
      await downloadProformaPdf(proformaId, invoiceNumber);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download proforma PDF.");
    }
  }

  const formValid =
    form.supplier_id && form.invoice_number.trim() && form.invoice_date && pdfFile;

  return (
    <Stack gap={6}>
      <ErrorNotice error={error} onClose={() => setError(null)} />

      <RecordWorkspace<Proforma>
        adapter={{
          resource: "proformas", title: "Proformas", singular: "proforma", breadcrumb: "Buy",
          description: "Review supplier documents and keep filed invoices organised.", defaultSort: "invoice_date",
          lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
          columns: [
            { key: "invoice_number", label: "Proforma", render: (item) => item.invoice_number },
            { key: "invoice_date", label: "Invoice date", render: (item) => item.invoice_date },
            { key: "currency", label: "Currency", render: (item) => item.currency },
          ],
          filters: [
            { key: "supplier_name", label: "Supplier", type: "text" },
            { key: "invoice_date", label: "Invoice date", type: "date" },
            { key: "currency", label: "Currency", type: "text" },
          ],
          actions: canMutate ? [{ key: "archive", label: "Archive" }, { key: "restore", label: "Restore" }] : [],
          getTitle: (item) => item.invoice_number, getSubtitle: (item) => item.supplier_name,
        } satisfies RecordWorkspaceAdapter<Proforma>}
        refreshKey={refreshKey}
        onCreate={canMutate ? openCreate : undefined}
        createLabel="File proforma"
        headerActions={canMutate ? <Button kind="tertiary" href="/proformas/read">Read a proforma</Button> : undefined}
        renderDetails={(item) => <Stack gap={5}>
          <RecordDetails>
            <RecordDetail label="Supplier">{item.supplier_name}</RecordDetail>
            <RecordDetail label="Invoice date">{item.invoice_date}</RecordDetail>
            <RecordDetail label="Currency">{item.currency}</RecordDetail>
            <RecordDetail label="Status">{item.is_archived ? "Archived" : "Active"}</RecordDetail>
          </RecordDetails>
          <Button kind="tertiary" onClick={() => void handleDownload(item.id, item.invoice_number)}>Download PDF</Button>
        </Stack>}
      />

      <Modal
        open={createOpen}
        modalHeading="File proforma invoice"
        primaryButtonText={saving ? "Filing…" : "File"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => { if (!saving) setCreateOpen(false); }}
        onRequestSubmit={() => void handleCreate()}
      >
        <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}><Stack gap={5}>
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
              disabled={saving}
              accept={["application/pdf", ".pdf"]}
              labelText="Drag and drop a PDF here or click to upload"
              multiple={false}
              onAddFiles={(_, { addedFiles }) => {
                if (saving) return;
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
                onDelete={() => { if (!saving) setPdfFile(null); }}
              />
            ) : null}
          </div>
        </Stack></fieldset>
      </Modal>
    </Stack>
  );
}
