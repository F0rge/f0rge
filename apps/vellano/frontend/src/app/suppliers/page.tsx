"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
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
  createSupplier,
  getSupplierLeadTimes,
  listSuppliers,
  type CreateSupplierPayload,
  type Supplier,
  type SupplierLeadTimeRow,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatObservedMedianLine, supplierLeadTimeById } from "@/lib/lead-times";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "default_currency", header: "Default currency" },
  { key: "observed_median", header: "Observed median" },
] as const;

type SupplierRow = {
  id: string;
  name: string;
  default_currency: string;
  observed_median: string;
};

const emptyCreateForm: CreateSupplierPayload = {
  name: "",
  default_currency: "",
};

export default function SuppliersPage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [leadTimes, setLeadTimes] = useState<SupplierLeadTimeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateSupplierPayload>(emptyCreateForm);
  const [saving, setSaving] = useState(false);

  const loadSuppliers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [data, leadReport] = await Promise.all([
        listSuppliers(),
        getSupplierLeadTimes().catch(() => ({ rows: [] as SupplierLeadTimeRow[] })),
      ]);
      setSuppliers(data);
      setLeadTimes(leadReport.rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load suppliers.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSuppliers();
    }
  }, [user, loadSuppliers]);

  const leadBySupplier = supplierLeadTimeById(leadTimes);
  const rows: SupplierRow[] = suppliers.map((entry) => ({
    id: entry.id,
    name: entry.name,
    default_currency: entry.default_currency,
    observed_median: formatObservedMedianLine(leadBySupplier.get(entry.id)),
  }));

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      const payload: CreateSupplierPayload = {
        name: createForm.name.trim(),
      };
      const currency = createForm.default_currency?.trim();
      if (currency) {
        payload.default_currency = currency;
      }
      await createSupplier(payload);
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadSuppliers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create supplier.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Suppliers</h1>
          <p className="cds--type-body-01">Furniture suppliers and their default currencies.</p>
        </div>
        {canMutate ? (
          <Button onClick={() => setCreateOpen(true)}>Add supplier</Button>
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
        <p className="cds--type-body-01">Loading suppliers…</p>
      ) : suppliers.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No suppliers"
          subtitle="No suppliers have been added yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Suppliers" description="All Vellano suppliers">
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
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>{cell.value}</TableCell>
                      ))}
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
        modalHeading="Add supplier"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createForm.name.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-supplier-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-supplier-currency"
            labelText="Default currency"
            helperText="Defaults to USD"
            value={createForm.default_currency ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, default_currency: event.target.value }))
            }
          />
        </Stack>
      </Modal>
    </Stack>
  );
}
