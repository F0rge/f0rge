"use client";

import { Printer } from "@carbon/icons-react";
import {
  Button,
  ComboBox,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
  Pagination,
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
import { useCallback, useEffect, useMemo, useRef, useState, Suspense } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  acceptQuote,
  canMutateQuotes,
  computeInvoicePreview,
  createQuote,
  downloadQuotePdf,
  exVatToIncVat,
  formatPriceAmount,
  formatZarAmount,
  incVatToExVat,
  parsePriceInput,
  isActiveLocation,
  listCustomers,
  listLocations,
  listPriceLists,
  listQuotes,
  listSkus,
  markQuoteSent,
  type CustomerCrm,
  type Location,
  type PriceList,
  type QuoteListItem,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  canEditQuoteDiscount,
  canOverrideQuoteUnitPrice,
  displayUnitAmount,
  formatQuoteSkuOption,
  formatUnitExVatInput,
  pricesIncludeVat,
  quoteLineExVat,
  quoteSkuMatchesQuery,
  quoteSkuUnitExVat,
  quoteUnitPriceHelper,
  vatBasisLabel,
} from "@/lib/quote-sku-price";

const TABLE_HEADERS = [
  { key: "quote_number", header: "Reference" },
  { key: "customer_name", header: "Customer" },
  { key: "items", header: "Items" },
  { key: "total_inc_vat", header: "Total" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Action" },
] as const;

type QuoteRow = {
  id: string;
  quote_number: string;
  customer_name: string;
  items: string;
  total_inc_vat: string;
  status: string;
  actions: string;
};

type LineForm = {
  sku_id: string;
  qty: number | "";
  unit_ex_vat: string;
  discount_percent: string;
  priceEdited: boolean;
};

const EMPTY_LINE: LineForm = {
  sku_id: "",
  qty: 1,
  unit_ex_vat: "",
  discount_percent: "0",
  priceEdited: false,
};

function pricedLine(
  line: LineForm,
  sku: Sku | undefined,
  customer: CustomerCrm | null,
  priceLists: PriceList[],
): LineForm {
  if (line.priceEdited || !sku) {
    return line;
  }
  const priced = quoteSkuUnitExVat(sku, customer, priceLists);
  return { ...line, unit_ex_vat: formatUnitExVatInput(priced.unitExVat) };
}

function QuotesPageInner() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateQuotes(user);
  const canOverridePrice = canOverrideQuoteUnitPrice(user?.role);
  const canEditDiscount = canEditQuoteDiscount(user?.role);
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [acceptOpen, setAcceptOpen] = useState<QuoteListItem | null>(null);
  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<LineForm[]>([{ ...EMPTY_LINE }]);
  const customerIdRef = useRef(customerId);
  customerIdRef.current = customerId;
  const [locationId, setLocationId] = useState("");
  const [holdStock, setHoldStock] = useState(true);
  const [depositAmount, setDepositAmount] = useState("");
  const [tender, setTender] = useState<"cash" | "eft">("eft");
  const [unitDrafts, setUnitDrafts] = useState<Record<number, string>>({});

  const loadQuotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pageData = await listQuotes({ limit: pageSize, offset: (page - 1) * pageSize });
      setQuotes(pageData.items);
      setTotal(pageData.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotes");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  const loadQuoteForm = useCallback(async () => {
    try {
      const [customerRows, skuRows, locationRows, priceListRows] = await Promise.all([
        listCustomers(),
        listSkus(),
        listLocations(),
        listPriceLists(),
      ]);
      setCustomers(customerRows);
      setSkus(skuRows);
      setPriceLists(priceListRows);
      setLocations(locationRows.filter(isActiveLocation));
      const walkIn = customerRows.find((row) => row.name === "Walk-in customer");
      const nextCustomerId = customerIdRef.current || walkIn?.id || "";
      if (nextCustomerId !== customerIdRef.current) {
        setCustomerId(nextCustomerId);
      }
      const customer = customerRows.find((row) => row.id === nextCustomerId) ?? null;
      setLines((current) =>
        current.map((line) =>
          pricedLine(
            line,
            skuRows.find((sku) => sku.id === line.sku_id),
            customer,
            priceListRows,
          ),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quote form");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadQuotes();
    }
  }, [user, loadQuotes]);

  useEffect(() => {
    if (user && (open || acceptOpen)) {
      void loadQuoteForm();
    }
  }, [user, open, acceptOpen, loadQuoteForm]);

  const rows: QuoteRow[] = useMemo(
    () =>
      quotes.map((quote) => ({
        id: quote.id,
        quote_number: quote.quote_number,
        customer_name: quote.customer_name,
        items: quote.items_label,
        total_inc_vat: formatZarAmount(quote.total_inc_vat),
        status: quote.status,
        actions: quote.id,
      })),
    [quotes],
  );

  const selectedCustomer = customers.find((row) => row.id === customerId) ?? null;
  const showInclusive = pricesIncludeVat(selectedCustomer);

  function shownUnit(ex: string): string {
    const parsed = parsePriceInput(ex);
    if (parsed === null) {
      return ex;
    }
    return formatPriceAmount(displayUnitAmount(parsed, showInclusive));
  }

  const quotePreview = useMemo(() => {
    const subtotal = lines.reduce(
      (sum, line) => sum + quoteLineExVat(line.qty, line.unit_ex_vat, line.discount_percent),
      0,
    );
    return { subtotal, ...computeInvoicePreview(subtotal) };
  }, [lines]);

  function applyCustomer(nextId: string) {
    const customer = customers.find((row) => row.id === nextId) ?? null;
    setUnitDrafts({});
    setCustomerId(nextId);
    setLines((current) =>
      current.map((line) =>
        pricedLine(
          line,
          skus.find((sku) => sku.id === line.sku_id),
          customer,
          priceLists,
        ),
      ),
    );
  }

  function selectSku(index: number, sku: Sku | null | undefined) {
    setLines((current) => {
      const next = [...current];
      const line = next[index];
      if (!line) {
        return current;
      }
      if (!sku) {
        next[index] = {
          ...line,
          sku_id: "",
          unit_ex_vat: line.priceEdited ? line.unit_ex_vat : "",
        };
        return next;
      }
      const priced = quoteSkuUnitExVat(sku, selectedCustomer, priceLists);
      next[index] = {
        ...line,
        sku_id: sku.id,
        unit_ex_vat: formatUnitExVatInput(priced.unitExVat),
        priceEdited: false,
      };
      return next;
    });
  }

  async function onCreate() {
    setError(null);
    if (!customerId) {
      setError("Choose a customer");
      return;
    }
    try {
      await createQuote({
        customer_id: customerId,
        lines: lines
          .filter((line) => line.sku_id && line.qty)
          .map((line) => ({
            sku_id: line.sku_id,
            qty: Number(line.qty),
            ...(canOverridePrice && line.unit_ex_vat.trim()
              ? { unit_ex_vat: line.unit_ex_vat.trim() }
              : {}),
            ...(canEditDiscount
              ? { discount_percent: line.discount_percent.trim() || "0" }
              : {}),
          })),
      });
      setOpen(false);
      await loadQuotes();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create quote");
    }
  }

  async function onAccept() {
    if (!acceptOpen) {
      return;
    }
    setError(null);
    try {
      const order = await acceptQuote(acceptOpen.id, {
        location_id: locationId || undefined,
        hold_stock: holdStock && Boolean(locationId),
        deposit: depositAmount
          ? { amount: depositAmount, tender }
          : undefined,
      });
      setAcceptOpen(null);
      router.push(`/orders?highlight=${order.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept quote");
    }
  }

  return (
    <Stack gap={5}>
      {error ? <InlineNotification kind="error" title={error} hideCloseButton /> : null}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Quotes</h1>
        {canMutate ? (
          <Button data-tour="quote-new" onClick={() => setOpen(true)}>New quote</Button>
        ) : null}
      </div>
      {loading ? <p className="cds--type-body-01">Loading quotes…</p> : null}
      <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
        {({ rows: tableRows, headers, getHeaderProps, getRowProps, getTableProps }) => (
          <TableContainer>
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {headers.map((header) => {
                    const { key, ...rest } = getHeaderProps({ header });
                    return (
                      <TableHeader key={key} {...rest}>
                        {header.header}
                      </TableHeader>
                    );
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map((row) => {
                  const quote = quotes.find((item) => item.id === row.id);
                  const { key, ...rowProps } = getRowProps({ row });
                  return (
                    <TableRow key={key} {...rowProps}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>
                          {cell.info.header === "actions" && quote ? (
                            <Stack gap={2} orientation="horizontal">
                              <Button
                                kind="ghost"
                                size="sm"
                                renderIcon={Printer}
                                iconDescription="PDF"
                                hasIconOnly
                                onClick={() => void downloadQuotePdf(quote.id, quote.quote_number)}
                              />
                              {canMutate && quote.status === "draft" ? (
                                <Button
                                  kind="ghost"
                                  size="sm"
                                  onClick={() => void markQuoteSent(quote.id).then(loadQuotes)}
                                >
                                  Mark sent
                                </Button>
                              ) : null}
                              {canMutate && (quote.status === "draft" || quote.status === "sent") ? (
                                <Button kind="primary" size="sm" onClick={() => setAcceptOpen(quote)}>
                                  Accept
                                </Button>
                              ) : null}
                            </Stack>
                          ) : (
                            cell.value
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
      <Pagination
        page={page}
        pageSize={pageSize}
        pageSizes={[10, 25, 50]}
        totalItems={total}
        onChange={({ page: nextPage, pageSize: nextSize }) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
      />
      <Modal
        open={open}
        modalHeading="New quote"
        primaryButtonText="Create"
        secondaryButtonText="Cancel"
        onRequestClose={() => setOpen(false)}
        onRequestSubmit={() => void onCreate()}
        size="lg"
      >
        <Stack gap={4}>
          <Select
            id="quote-customer"
            labelText="Customer"
            value={customerId}
            onChange={(event) => applyCustomer(event.target.value)}
          >
            <SelectItem value="" text="No customer (retail incl. VAT)" />
            {customers.map((customer) => (
              <SelectItem key={customer.id} value={customer.id} text={customer.name} />
            ))}
          </Select>
          <p className="cds--type-helper-text-01">
            Retail unit prices are shown incl. VAT. Stockist, Wholesale, and Decorator unit prices
            are shown excl. VAT, and VAT is added on the total. A price list overrides the
            classification. A missing tier price falls back to Retail and is marked on the line.
            {canOverridePrice
              ? " You can edit the unit price."
              : " The unit price is read-only. Only the owner can change it."}
            {canEditDiscount
              ? " A discount is a percent off the line. The unit price stays the same."
              : " The discount is read-only. Only the owner, till, or warehouse can change it."}
          </p>
          {lines.map((line, index) => {
            const sku = skus.find((item) => item.id === line.sku_id);
            const priced = sku ? quoteSkuUnitExVat(sku, selectedCustomer, priceLists) : null;
            return (
              <div
                key={index}
                style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(0, 2fr) 6rem 9rem 7rem",
                  gap: "0.75rem",
                  alignItems: "start",
                }}
              >
                <ComboBox
                  id={`quote-sku-${index}`}
                  titleText="SKU"
                  placeholder="Search by code, barcode, or name"
                  items={skus}
                  itemToString={(item) =>
                    item ? formatQuoteSkuOption(item, selectedCustomer, priceLists) : ""
                  }
                  selectedItem={sku ?? null}
                  shouldFilterItem={({ item, inputValue }) =>
                    quoteSkuMatchesQuery(
                      item,
                      inputValue,
                      formatQuoteSkuOption(item, selectedCustomer, priceLists),
                    )
                  }
                  onChange={({ selectedItem }) => selectSku(index, selectedItem)}
                />
                <NumberInput
                  id={`quote-qty-${index}`}
                  label="Qty"
                  min={1}
                  value={line.qty}
                  onChange={(_, { value }) => {
                    const next = [...lines];
                    next[index] = { ...next[index], qty: value === "" ? "" : Number(value) };
                    setLines(next);
                  }}
                />
                <TextInput
                  id={`quote-unit-${index}`}
                  labelText={`Unit ${vatBasisLabel(showInclusive)}`}
                  value={unitDrafts[index] ?? shownUnit(line.unit_ex_vat)}
                  readOnly={!canOverridePrice}
                  helperText={
                    priced?.warning
                      ? priced.warning
                      : !canOverridePrice
                        ? priced
                          ? `${quoteUnitPriceHelper(priced, Boolean(selectedCustomer))} · read-only`
                          : `${vatBasisLabel(showInclusive)} · read-only`
                        : line.priceEdited
                          ? `${vatBasisLabel(showInclusive)} — edited`
                          : priced
                            ? quoteUnitPriceHelper(priced, Boolean(selectedCustomer))
                            : vatBasisLabel(showInclusive)
                  }
                  onFocus={() => {
                    if (!canOverridePrice) {
                      return;
                    }
                    setUnitDrafts((current) => ({
                      ...current,
                      [index]: shownUnit(line.unit_ex_vat),
                    }));
                  }}
                  onChange={(event) => {
                    if (!canOverridePrice) {
                      return;
                    }
                    setUnitDrafts((current) => ({ ...current, [index]: event.target.value }));
                  }}
                  onBlur={() => {
                    const draft = unitDrafts[index];
                    if (draft === undefined) {
                      return;
                    }
                    const parsed = parsePriceInput(draft);
                    const stored =
                      parsed === null
                        ? ""
                        : formatPriceAmount(showInclusive ? incVatToExVat(parsed) : parsed);
                    const previousAmount = parsePriceInput(line.unit_ex_vat);
                    const previousText =
                      previousAmount === null ? "" : formatPriceAmount(previousAmount);
                    const next = [...lines];
                    next[index] = {
                      ...next[index],
                      unit_ex_vat: stored,
                      priceEdited: stored !== previousText,
                    };
                    setLines(next);
                    setUnitDrafts((current) => {
                      const rest = { ...current };
                      delete rest[index];
                      return rest;
                    });
                  }}
                />
                <TextInput
                  id={`quote-discount-${index}`}
                  labelText="Discount %"
                  value={line.discount_percent}
                  readOnly={!canEditDiscount}
                  helperText={
                    canEditDiscount
                      ? "Percent off the line"
                      : "Read-only"
                  }
                  onChange={(event) => {
                    if (!canEditDiscount) {
                      return;
                    }
                    const next = [...lines];
                    next[index] = { ...next[index], discount_percent: event.target.value };
                    setLines(next);
                  }}
                />
              </div>
            );
          })}
          <Button kind="tertiary" size="sm" onClick={() => setLines([...lines, { ...EMPTY_LINE }])}>
            Add line
          </Button>
          <p className="cds--type-body-01">
            {showInclusive ? "Unit prices incl. VAT. " : "Unit prices excl. VAT. "}
            Ex VAT: R {formatPriceAmount(quotePreview.subtotal)} · VAT 15%: R{" "}
            {formatPriceAmount(quotePreview.vat)} · Total incl. VAT: R{" "}
            {formatPriceAmount(quotePreview.totalIncVat)}
          </p>
        </Stack>
      </Modal>
      <Modal
        open={Boolean(acceptOpen)}
        modalHeading="Accept quote"
        primaryButtonText="Accept"
        secondaryButtonText="Cancel"
        onRequestClose={() => setAcceptOpen(null)}
        onRequestSubmit={() => void onAccept()}
      >
        <Stack gap={4}>
          <Select
            id="accept-location"
            labelText="Hold location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
          >
            <SelectItem value="" text="No hold" />
            {locations.map((location) => (
              <SelectItem key={location.id} value={location.id} text={`${location.name} (${location.type})`} />
            ))}
          </Select>
          <Select
            id="accept-hold"
            labelText="Hold stock"
            value={holdStock ? "yes" : "no"}
            onChange={(event) => setHoldStock(event.target.value === "yes")}
          >
            <SelectItem value="yes" text="Yes" />
            <SelectItem value="no" text="No" />
          </Select>
          <TextInput
            id="accept-deposit"
            labelText="Deposit (optional)"
            value={depositAmount}
            onChange={(event) => setDepositAmount(event.target.value)}
          />
          <Select id="accept-tender" labelText="Tender" value={tender} onChange={(event) => setTender(event.target.value as "cash" | "eft")}>
            <SelectItem value="eft" text="EFT" />
            <SelectItem value="cash" text="Cash" />
          </Select>
        </Stack>
      </Modal>
    </Stack>
  );
}

export default function QuotesPage() {
  return (
    <Suspense>
      <QuotesPageInner />
    </Suspense>
  );
}
