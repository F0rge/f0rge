"use client";

import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
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
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  PO_STATUS_LABELS,
  canRaisePo,
  canReceive,
  downloadPackingSheet,
  getPurchaseOrder,
  landPurchaseOrder,
  listSuppliers,
  markOnWater,
  type PurchaseOrder,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type BillForm = {
  invoice_number: string;
  amount: string;
  currency: string;
  file: File | null;
};

const emptyBill = (currency = "USD"): BillForm => ({
  invoice_number: "",
  amount: "",
  currency,
  file: null,
});

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canRaise = canRaisePo(user);
  const canRecv = canReceive(user);
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [landOpen, setLandOpen] = useState(false);
  const [fxToZar, setFxToZar] = useState("");
  const [factoryBill, setFactoryBill] = useState<BillForm>(emptyBill("USD"));
  const [freightBill, setFreightBill] = useState<BillForm>(emptyBill("USD"));
  const [clearanceBill, setClearanceBill] = useState<BillForm>(emptyBill("ZAR"));

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPurchaseOrder(params.id);
      setOrder(data);
      const suppliers = await listSuppliers();
      const matched = suppliers.find((entry) => entry.id === data.supplier_id) ?? null;
      setSupplier(matched);
      if (matched) {
        setFactoryBill((current) => ({ ...current, currency: matched.default_currency }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load purchase order.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadOrder();
    }
  }, [user, params.id, loadOrder]);

  async function handleDownload() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await downloadPackingSheet(order.id, order.po_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download packing sheet.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleMarkOnWater() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await markOnWater(order.id);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark on water.");
    } finally {
      setActionLoading(false);
    }
  }

  function openLandModal() {
    setFxToZar("");
    setFactoryBill(emptyBill(supplier?.default_currency ?? "USD"));
    setFreightBill(emptyBill("USD"));
    setClearanceBill(emptyBill("ZAR"));
    setLandOpen(true);
  }

  function billValid(bill: BillForm): boolean {
    return Boolean(bill.invoice_number.trim() && bill.amount.trim() && bill.currency.trim() && bill.file);
  }

  const landValid = fxToZar.trim() && billValid(factoryBill) && billValid(freightBill) && billValid(clearanceBill);

  async function handleLand() {
    if (!order || !landValid) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("fx_to_zar", fxToZar.trim());
      formData.append("factory_invoice_number", factoryBill.invoice_number.trim());
      formData.append("factory_amount", factoryBill.amount.trim());
      formData.append("factory_currency", factoryBill.currency.trim());
      formData.append("factory_file", factoryBill.file as File);
      formData.append("freight_invoice_number", freightBill.invoice_number.trim());
      formData.append("freight_amount", freightBill.amount.trim());
      formData.append("freight_currency", freightBill.currency.trim());
      formData.append("freight_file", freightBill.file as File);
      formData.append("clearance_invoice_number", clearanceBill.invoice_number.trim());
      formData.append("clearance_amount", clearanceBill.amount.trim());
      formData.append("clearance_currency", clearanceBill.currency.trim());
      formData.append("clearance_file", clearanceBill.file as File);
      const updated = await landPurchaseOrder(order.id, formData);
      setOrder(updated);
      setLandOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to land costs.");
    } finally {
      setActionLoading(false);
    }
  }

  function renderBillSection(
    label: string,
    bill: BillForm,
    setBill: (value: BillForm) => void,
    fileKey: string,
  ) {
    return (
      <Stack gap={4}>
        <p className="cds--type-productive-heading-02">{label}</p>
        <TextInput
          id={`${fileKey}-invoice`}
          labelText="Invoice number"
          value={bill.invoice_number}
          onChange={(event) => setBill({ ...bill, invoice_number: event.target.value })}
          required
        />
        <TextInput
          id={`${fileKey}-amount`}
          labelText="Amount"
          value={bill.amount}
          onChange={(event) => setBill({ ...bill, amount: event.target.value })}
          required
        />
        <TextInput
          id={`${fileKey}-currency`}
          labelText="Currency"
          value={bill.currency}
          onChange={(event) => setBill({ ...bill, currency: event.target.value })}
          required
        />
        <div>
          <p className="cds--label">PDF</p>
          <FileUploaderDropContainer
            accept={["application/pdf", ".pdf"]}
            labelText="Upload PDF"
            multiple={false}
            onAddFiles={(_, { addedFiles }) => {
              const file = addedFiles[0];
              if (file && !file.invalidFileType) {
                setBill({ ...bill, file });
              }
            }}
          />
          {bill.file ? (
            <FileUploaderItem
              name={bill.file.name}
              status="complete"
              onDelete={() => setBill({ ...bill, file: null })}
            />
          ) : null}
        </div>
      </Stack>
    );
  }

  if (loading) {
    return <p className="cds--type-body-01">Loading purchase order…</p>;
  }

  if (!order) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle="Purchase order could not be loaded."
        hideCloseButton
        lowContrast
      />
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <Button kind="ghost" size="sm" onClick={() => router.push("/purchase-orders")}>
          ← Back to purchase orders
        </Button>
        <h1 className="cds--type-productive-heading-04" style={{ marginTop: "0.5rem" }}>
          {order.po_number}
        </h1>
        <p className="cds--type-body-01">
          {order.supplier_name} · {PO_STATUS_LABELS[order.status]}
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

      <Stack gap={4} orientation="horizontal">
        <Button kind="secondary" disabled={actionLoading} onClick={() => void handleDownload()}>
          Download packing sheet
        </Button>
        {canRaise && order.status === "open" ? (
          <Button disabled={actionLoading} onClick={() => void handleMarkOnWater()}>
            Mark on water
          </Button>
        ) : null}
        {canRaise && order.status === "on_water" ? (
          <Button disabled={actionLoading} onClick={openLandModal}>
            Land costs
          </Button>
        ) : null}
        {canRecv && order.status === "landed" ? (
          <Button
            kind="primary"
            disabled={actionLoading}
            onClick={() => router.push(`/receive?po=${order.id}`)}
          >
            Receive
          </Button>
        ) : null}
      </Stack>
      <p className="cds--type-helper-text-01">
        Download or print. The app does not send email.
      </p>

      <TableContainer title="Lines" description="PO line items">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Our ref</TableHeader>
              <TableHeader>Our barcode</TableHeader>
              <TableHeader>Name</TableHeader>
              <TableHeader>Fabric</TableHeader>
              <TableHeader>Qty</TableHeader>
              <TableHeader>Factory unit</TableHeader>
              <TableHeader>Unit cost ZAR</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {order.lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>{line.our_ref}</TableCell>
                <TableCell>{line.our_barcode}</TableCell>
                <TableCell>{line.name}</TableCell>
                <TableCell>{line.fabric}</TableCell>
                <TableCell>{line.qty}</TableCell>
                <TableCell>{line.factory_unit_amount}</TableCell>
                <TableCell>{line.unit_cost_zar ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {order.bills.length > 0 ? (
        <TableContainer title="Landing bills" description="Factory, freight, and clearance">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Kind</TableHeader>
                <TableHeader>Invoice number</TableHeader>
                <TableHeader>Amount</TableHeader>
                <TableHeader>Currency</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {order.bills.map((bill, index) => (
                <TableRow key={`${bill.kind}-${index}`}>
                  <TableCell>{bill.kind}</TableCell>
                  <TableCell>{bill.invoice_number}</TableCell>
                  <TableCell>{bill.amount}</TableCell>
                  <TableCell>{bill.currency}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      <Modal
        open={landOpen}
        modalHeading="Land costs"
        primaryButtonText={actionLoading ? "Landing…" : "Land"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={actionLoading || !landValid}
        onRequestClose={() => setLandOpen(false)}
        onRequestSubmit={() => void handleLand()}
        size="lg"
      >
        <Stack gap={6}>
          <TextInput
            id="land-fx"
            labelText="FX to ZAR"
            helperText="ZAR per 1 unit of foreign currency"
            value={fxToZar}
            onChange={(event) => setFxToZar(event.target.value)}
            required
          />
          {renderBillSection("Factory", factoryBill, setFactoryBill, "factory")}
          {renderBillSection("Freight", freightBill, setFreightBill, "freight")}
          {renderBillSection("Clearance", clearanceBill, setClearanceBill, "clearance")}
        </Stack>
      </Modal>
    </Stack>
  );
}
