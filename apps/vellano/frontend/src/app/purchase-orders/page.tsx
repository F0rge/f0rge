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
  ApiError,
  PO_STATUS_LABELS,
  canRaisePo,
  createPurchaseOrder,
  listProformas,
  listPurchaseOrders,
  listSkus,
  listSuppliers,
  type CreatePoLinePayload,
  type Proforma,
  type PurchaseOrder,
  type Sku,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "po_number", header: "PO number" },
  { key: "supplier_name", header: "Supplier" },
  { key: "status", header: "Status" },
  { key: "line_count", header: "Lines" },
  { key: "created_at", header: "Created" },
  { key: "actions", header: "" },
] as const;

type PoRow = {
  id: string;
  po_number: string;
  supplier_name: string;
  status: string;
  line_count: string;
  created_at: string;
  actions: string;
};

type PoLineForm = {
  sku_id: string;
  qty: number | "";
  factory_unit_amount: string;
};

const emptyLine = (): PoLineForm => ({
  sku_id: "",
  qty: "",
  factory_unit_amount: "",
});

function formatDate(iso: string): string {
  return iso.slice(0, 10);
}

export default function PurchaseOrdersPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canRaise = canRaisePo(user);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [proformas, setProformas] = useState<Proforma[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [supplierId, setSupplierId] = useState("");
  const [proformaId, setProformaId] = useState("");
  const [lines, setLines] = useState<PoLineForm[]>([emptyLine(), emptyLine()]);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPurchaseOrders();
      setOrders(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load purchase orders.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadOrders();
    }
  }, [user, loadOrders]);

  const loadCreateData = useCallback(async () => {
    try {
      const [supplierData, proformaData, skuData] = await Promise.all([
        listSuppliers(),
        listProformas(),
        listSkus(),
      ]);
      setSuppliers(supplierData);
      setProformas(proformaData);
      setSkus(skuData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load form data.");
    }
  }, []);

  useEffect(() => {
    if (createOpen && canRaise) {
      void loadCreateData();
    }
  }, [createOpen, canRaise, loadCreateData]);

  const filteredProformas = proformas.filter((entry) => entry.supplier_id === supplierId);

  function resetCreateForm() {
    setSupplierId("");
    setProformaId("");
    setLines([emptyLine(), emptyLine()]);
  }

  function openCreate() {
    resetCreateForm();
    setSuccess(null);
    setCreateOpen(true);
  }

  function updateLine(index: number, patch: Partial<PoLineForm>) {
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

  const linesValid = lines.every(
    (line) =>
      line.sku_id &&
      typeof line.qty === "number" &&
      line.qty > 0 &&
      line.factory_unit_amount.trim() !== "",
  );
  const formValid = supplierId && lines.length >= 1 && linesValid;

  async function handleCreate() {
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        supplier_id: supplierId,
        proforma_id: proformaId || undefined,
        lines: lines.map(
          (line): CreatePoLinePayload => ({
            sku_id: line.sku_id,
            qty: line.qty as number,
            factory_unit_amount: line.factory_unit_amount.trim(),
          }),
        ),
      };
      const created = await createPurchaseOrder(payload);
      setCreateOpen(false);
      resetCreateForm();
      setSuccess(`Purchase order ${created.po_number} created.`);
      await loadOrders();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create purchase order.");
      }
    } finally {
      setSaving(false);
    }
  }

  const rows: PoRow[] = orders.map((entry) => ({
    id: entry.id,
    po_number: entry.po_number,
    supplier_name: entry.supplier_name,
    status: PO_STATUS_LABELS[entry.status],
    line_count: String(entry.lines.length),
    created_at: formatDate(entry.created_at),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Purchase orders</h1>
          <p className="cds--type-body-01">
            Raise POs, mark on water, land costs, and receive stock.
          </p>
        </div>
        {canRaise ? <Button onClick={openCreate}>Raise PO</Button> : null}
      </div>

      {success ? (
        <InlineNotification
          kind="success"
          title="Created"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

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
        <p className="cds--type-body-01">Loading purchase orders…</p>
      ) : orders.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No purchase orders"
          subtitle="No purchase orders have been raised yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Purchase orders" description="All Vellano purchase orders">
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
                      onClick={() => router.push(`/purchase-orders/${row.id}`)}
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
                                  router.push(`/purchase-orders/${row.id}`);
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
        modalHeading="Raise PO"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <Select
            id="po-supplier"
            labelText="Supplier"
            value={supplierId}
            onChange={(event) => {
              setSupplierId(event.target.value);
              setProformaId("");
            }}
          >
            <SelectItem value="" text="Select a supplier" />
            {suppliers.map((supplier) => (
              <SelectItem key={supplier.id} value={supplier.id} text={supplier.name} />
            ))}
          </Select>
          <Select
            id="po-proforma"
            labelText="Proforma (optional)"
            value={proformaId}
            disabled={!supplierId}
            onChange={(event) => setProformaId(event.target.value)}
          >
            <SelectItem value="" text="None" />
            {filteredProformas.map((proforma) => (
              <SelectItem
                key={proforma.id}
                value={proforma.id}
                text={`${proforma.invoice_number} (${proforma.invoice_date})`}
              />
            ))}
          </Select>
          <div>
            <p className="cds--label">Lines</p>
            <p className="cds--helper-text">At least one SKU line.</p>
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
                  <Select
                    id={`po-line-sku-${index}`}
                    labelText={index === 0 ? "SKU" : ""}
                    hideLabel={index > 0}
                    value={line.sku_id}
                    onChange={(event) => updateLine(index, { sku_id: event.target.value })}
                  >
                    <SelectItem value="" text="Select SKU" />
                    {skus.map((sku) => (
                      <SelectItem
                        key={sku.id}
                        value={sku.id}
                        text={`${sku.our_ref} — ${sku.name}`}
                      />
                    ))}
                  </Select>
                  <NumberInput
                    id={`po-line-qty-${index}`}
                    label={index === 0 ? "Qty" : ""}
                    hideLabel={index > 0}
                    min={1}
                    value={line.qty}
                    onChange={(_, { value }) =>
                      updateLine(index, { qty: value === "" ? "" : Number(value) })
                    }
                  />
                  <TextInput
                    id={`po-line-factory-${index}`}
                    labelText={index === 0 ? "Factory unit" : ""}
                    hideLabel={index > 0}
                    value={line.factory_unit_amount}
                    onChange={(event) =>
                      updateLine(index, { factory_unit_amount: event.target.value })
                    }
                  />
                  {lines.length > 1 ? (
                    <Button
                      kind="ghost"
                      size="sm"
                      onClick={() => removeLine(index)}
                      style={{ marginBottom: "0.25rem" }}
                    >
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
