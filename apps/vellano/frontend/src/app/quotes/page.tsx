"use client";

import { Printer } from "@carbon/icons-react";
import {
  Button,
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
import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { useRouter } from "next/navigation";

import {
  ApiError,
  acceptQuote,
  canMutateQuotes,
  createQuote,
  downloadQuotePdf,
  formatZarAmount,
  isActiveLocation,
  listCustomers,
  listLocations,
  listQuotes,
  listSkus,
  markQuoteSent,
  type CustomerCrm,
  type Location,
  type QuoteListItem,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

type LineForm = { sku_id: string; qty: number | "" };

function QuotesPageInner() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateQuotes(user);
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [acceptOpen, setAcceptOpen] = useState<QuoteListItem | null>(null);
  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<LineForm[]>([{ sku_id: "", qty: 1 }]);
  const [locationId, setLocationId] = useState("");
  const [holdStock, setHoldStock] = useState(true);
  const [depositAmount, setDepositAmount] = useState("");
  const [tender, setTender] = useState<"cash" | "eft">("eft");

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
      const [customerRows, skuRows, locationRows] = await Promise.all([
        listCustomers(),
        listSkus(),
        listLocations(),
      ]);
      setCustomers(customerRows);
      setSkus(skuRows);
      setLocations(locationRows.filter(isActiveLocation));
      const walkIn = customerRows.find((row) => row.name === "Walk-in customer");
      if (walkIn) {
        setCustomerId((current) => current || walkIn.id);
      }
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

  async function onCreate() {
    setError(null);
    try {
      await createQuote({
        customer_id: customerId,
        lines: lines
          .filter((line) => line.sku_id && line.qty)
          .map((line) => ({ sku_id: line.sku_id, qty: Number(line.qty) })),
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
          <Button onClick={() => setOpen(true)}>New quote</Button>
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
      >
        <Stack gap={4}>
          <Select
            id="quote-customer"
            labelText="Customer"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
          >
            {customers.map((customer) => (
              <SelectItem key={customer.id} value={customer.id} text={customer.name} />
            ))}
          </Select>
          {lines.map((line, index) => (
            <Stack key={index} gap={3} orientation="horizontal">
              <Select
                id={`quote-sku-${index}`}
                labelText="SKU"
                value={line.sku_id}
                onChange={(event) => {
                  const next = [...lines];
                  next[index] = { ...next[index], sku_id: event.target.value };
                  setLines(next);
                }}
              >
                <SelectItem value="" text="Select SKU" />
                {skus.map((sku) => (
                  <SelectItem key={sku.id} value={sku.id} text={`${sku.our_ref} — ${sku.name}`} />
                ))}
              </Select>
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
            </Stack>
          ))}
          <Button kind="tertiary" size="sm" onClick={() => setLines([...lines, { sku_id: "", qty: 1 }])}>
            Add line
          </Button>
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
