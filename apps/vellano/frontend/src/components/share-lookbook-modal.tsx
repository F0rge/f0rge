"use client";

import {
  ComboBox,
  InlineNotification,
  Modal,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createLookbook,
  listCustomers,
  listPriceLists,
  lookbookPublicUrl,
  type CustomerCrm,
  type Lookbook,
  type LookbookPriceMode,
  type PriceList,
} from "@/lib/api";

const WALK_IN_SENTINEL: CustomerCrm = {
  id: "",
  name: "Walk-in (no CRM record)",
  email: null,
  phone: null,
  vat_number: null,
  billing_address: null,
  customer_type: "retail",
  price_tier: "standard",
  open_invoices_count: 0,
  open_invoices_zar: "0",
  overdue_invoices_count: 0,
  overdue_invoices_zar: "0",
  active_laybys_count: 0,
  active_laybys_zar: "0",
  last_purchase_date: null,
  credit_limit: null,
  on_hold: false,
  on_hold_reason: null,
  payment_terms_days: null,
  price_list_id: null,
  created_at: "",
  updated_at: "",
};

function customerItemToString(item: CustomerCrm | null): string {
  return item ? item.name : "";
}

function filterCustomerItem({
  item,
  inputValue,
}: {
  item: CustomerCrm;
  inputValue: string | null;
}): boolean {
  const query = (inputValue ?? "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  return (
    item.name.toLowerCase().includes(query) ||
    (item.email ?? "").toLowerCase().includes(query) ||
    (item.phone ?? "").toLowerCase().includes(query)
  );
}

type ShareLookbookModalProps = {
  open: boolean;
  skuIds: string[];
  defaultName: string;
  onClose: () => void;
  onCreated?: (lookbook: Lookbook) => void;
};

export function ShareLookbookModal({
  open,
  skuIds,
  defaultName,
  onClose,
  onCreated,
}: ShareLookbookModalProps) {
  const [name, setName] = useState(defaultName);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [customer, setCustomer] = useState<CustomerCrm>(WALK_IN_SENTINEL);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [priceMode, setPriceMode] = useState<LookbookPriceMode>("retail");
  const [priceListId, setPriceListId] = useState("");
  const [expiresInDays, setExpiresInDays] = useState<number | "">(14);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const customerItems = useMemo(() => [WALK_IN_SENTINEL, ...customers.filter((row) => row.id)], [customers]);

  const loadForm = useCallback(async () => {
    try {
      const [customerRows, lists] = await Promise.all([listCustomers(), listPriceLists()]);
      setCustomers(customerRows.filter((row) => row.name !== "Walk-in customer"));
      setPriceLists(lists);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load share form");
    }
  }, []);

  useEffect(() => {
    if (open) {
      setName(defaultName);
      setCustomer(WALK_IN_SENTINEL);
      setPriceMode("retail");
      setPriceListId("");
      setExpiresInDays(14);
      setError(null);
      setCopied(null);
      void loadForm();
    }
  }, [open, defaultName, loadForm]);

  async function onSubmit() {
    if (skuIds.length === 0) {
      setError("Select or filter SKUs before sharing.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const lookbook = await createLookbook({
        name: name.trim() || defaultName,
        customer_id: customer.id || undefined,
        price_mode: priceMode,
        price_list_id: priceMode === "price_list" ? priceListId : undefined,
        sku_ids: skuIds,
        expires_in_days: typeof expiresInDays === "number" ? expiresInDays : 14,
      });
      const url = lookbookPublicUrl(lookbook.token);
      try {
        await navigator.clipboard.writeText(url);
        setCopied(url);
      } catch {
        setCopied(url);
      }
      onCreated?.(lookbook);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not share lookbook");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      modalHeading="Share lookbook"
      primaryButtonText={copied ? "Done" : "Create and copy link"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={
        submitting ||
        skuIds.length === 0 ||
        (!copied && priceMode === "price_list" && !priceListId)
      }
      onRequestClose={onClose}
      onRequestSubmit={() => {
        if (copied) {
          onClose();
          return;
        }
        void onSubmit();
      }}
    >
      <Stack gap={4}>
        {error ? (
          <InlineNotification
            kind="error"
            title="Could not share"
            subtitle={error}
            onCloseButtonClick={() => setError(null)}
            lowContrast
          />
        ) : null}
        {copied ? (
          <InlineNotification
            kind="success"
            title="Link copied"
            subtitle={copied}
            hideCloseButton
            lowContrast
          />
        ) : null}
        <p className="cds--type-body-01">
          {skuIds.length} SKU{skuIds.length === 1 ? "" : "s"} — selected rows if any, otherwise the
          current filter result. Attach a CRM customer or leave as walk-in.
        </p>
        <TextInput
          id="lookbook-name"
          labelText="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <ComboBox
          id="lookbook-customer"
          titleText="Customer (optional)"
          placeholder="Walk-in or search CRM…"
          items={customerItems}
          itemToString={customerItemToString}
          selectedItem={customer}
          shouldFilterItem={filterCustomerItem}
          onChange={({ selectedItem }) => setCustomer(selectedItem ?? WALK_IN_SENTINEL)}
        />
        <Select
          id="lookbook-price-mode"
          labelText="Prices to show"
          value={priceMode}
          onChange={(event) => setPriceMode(event.target.value as LookbookPriceMode)}
        >
          <SelectItem value="retail" text="Retail inc VAT" />
          <SelectItem value="price_list" text="Named price list" />
          <SelectItem value="hidden" text="Hide prices" />
        </Select>
        {priceMode === "price_list" ? (
          <Select
            id="lookbook-price-list"
            labelText="Price list"
            value={priceListId}
            onChange={(event) => setPriceListId(event.target.value)}
          >
            <SelectItem value="" text="Select a price list" />
            {priceLists.map((list) => (
              <SelectItem key={list.id} value={list.id} text={list.name} />
            ))}
          </Select>
        ) : null}
        <NumberInput
          id="lookbook-expiry"
          label="Expires in days"
          min={1}
          max={90}
          value={expiresInDays}
          onChange={(_, { value }) => setExpiresInDays(value === "" ? "" : Number(value))}
        />
      </Stack>
    </Modal>
  );
}
