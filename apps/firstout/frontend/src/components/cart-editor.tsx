"use client";

import {
  Button,
  ClickableTile,
  ComboBox,
  InlineNotification,
  NumberInput,
  Pagination,
  Select,
  SelectItem,
  Stack,
  Tag,
  TextArea,
  Tile,
} from "@carbon/react";
import { SkuLink } from "@/components/sku-link";
import { useWidePage } from "@/components/sku-panel/provider";
import {
  Image as ImageIcon,
  Locked,
  Purchase,
  TrashCan,
  UserFollow,
} from "@carbon/icons-react";
import { useState, type ReactNode } from "react";

import { CustomerPicker } from "@/components/customer-picker";
import { StaffImage } from "@/components/staff-image";
import {
  INVOICE_NOTE_MAX,
  formatPriceAmount,
  formatZarAmount,
  skuPhotoUrl,
  vatPercentLabel,
  type CustomerCrm,
  type SalesStaffOption,
  type Sku,
  type SalePricePreview,
} from "@/lib/api";
import { alignPreviewLines, blockedReason } from "@/lib/sale-preview";
import {
  lineQuantityNotice,
  quantityInputBounds,
  quantityRuleHelper,
  startQty,
  type QuantityRuleRefusal,
} from "@/lib/sale-quantity-rule";
import { commissionBase, rememberColleague, zar } from "@/lib/sales-staff";
import styles from "./cart-editor.module.css";

/** The till's sale builder. Quotes and invoices reuse it; the till adds stock, scanning and payment. */
export type CartMode = "till" | "quote" | "invoice";

export type CartLine = {
  key: string;
  sku: Sku;
  qty: number;
  discountPercent: number;
};

/** A search result; reserved SKUs stay listed but cannot be chosen. */
type SkuOption = Sku & { disabled?: boolean; reason?: string };

const DOCUMENT: Record<CartMode, string> = { till: "invoice", quote: "quote", invoice: "invoice" };

export function clampDiscount(value: number): number {
  if (value < 0) {
    return 0;
  }
  if (value > 100) {
    return 100;
  }
  return value;
}

export function mergeCartBySku(current: CartLine[], sku: Sku, addQty: number): CartLine[] {
  if (sku.is_archived) return current;
  const existing = current.find((line) => line.sku.id === sku.id);
  if (existing) {
    return current.map((line) =>
      line.sku.id === sku.id ? { ...line, qty: line.qty + addQty } : line,
    );
  }
  return [...current, { key: sku.id, sku, qty: addQty, discountPercent: 0 }];
}

function skuItemToString(item: Sku | null): string {
  return item ? `${item.our_ref} — ${item.name}` : "";
}

function filterSkuItem({ item, inputValue }: { item: Sku; inputValue: string | null }): boolean {
  const query = (inputValue ?? "").trim().toLowerCase();
  if (!query) {
    return true;
  }
  return (
    item.name.toLowerCase().includes(query) ||
    item.our_ref.toLowerCase().includes(query) ||
    item.our_barcode.toLowerCase().includes(query)
  );
}

function SkuThumb({ sku }: { sku: Sku }) {
  if (!sku.photo_storage_key) {
    return (
      <div className="firstout-till-thumb firstout-till-thumb--placeholder" aria-hidden>
        <ImageIcon size={20} />
      </div>
    );
  }
  return (
    <StaffImage className="firstout-till-thumb" src={skuPhotoUrl(sku.id)} alt="" width={48} height={48} />
  );
}

export type CartEditorProps = {
  mode: CartMode;
  /** Heading of the cart panel. */
  title?: string;
  /** Products the finder offers; the caller decides what can be sold and priced here (`mayBePriced`). */
  products: Sku[];
  cart: CartLine[];
  onAdd: (sku: Sku, qty: number) => boolean;
  onUpdateLine: (key: string, patch: Partial<Pick<CartLine, "qty" | "discountPercent">>) => void;
  onRemoveLine: (key: string) => void;
  /** The finder's chosen product and quantity, kept by the caller so it can clear them. */
  skuId: string;
  onSkuIdChange: (id: string) => void;
  qty: number | "";
  onQtyChange: (qty: number | "") => void;
  customers: CustomerCrm[];
  customerId: string;
  onCustomerChange: (id: string) => void;
  selectedCustomer: CustomerCrm | null;
  /** Opens the new-customer form; the cart opens it in a new tab when absent. */
  onAddCustomer?: () => void;
  onBrowseCatalogue?: () => void;
  /** The server's prices for `cart`, then any `afterLines` lines, in that order (ADR 0001). */
  preview?: SalePricePreview;
  pricingError?: string;
  onRetryPricing: () => void;
  canDiscount: boolean;
  colleagues: SalesStaffOption[] | null;
  colleaguesError: boolean;
  salesStaffId: string;
  onSalesStaffChange: (id: string) => void;
  notePrinted: string;
  onNotePrintedChange: (value: string) => void;
  noteInternal: string;
  onNoteInternalChange: (value: string) => void;
  /** The search and quantity fields, e.g. while the till has no showroom. */
  searchDisabled?: boolean;
  /** Adding from the product tiles, e.g. while the till basket loads. */
  addDisabled?: boolean;
  /** The finder quantity's upper bound for this product. */
  qtyMax?: (sku: Sku) => number | undefined;
  /** A cart line's quantity bound. */
  lineQtyMax?: (sku: Sku) => number | undefined;
  /** False when that quantity cannot be added (e.g. not enough floor stock). */
  canAddQty?: (sku: Sku, qty: number) => boolean;
  /** Why a product cannot be chosen (reserved by another sale); listed but disabled. */
  blockedReason?: (sku: Sku) => string | null;
  /** The quiet stock line under a result or tile. */
  stockState?: (sku: Sku) => string;
  tileDisabled?: (sku: Sku) => boolean;
  /** Staff-only note under a cart line's SKU (stock location). */
  lineNote?: (line: CartLine) => ReactNode;
  /** Above the product search (showroom and scanning at the till). */
  finderTop?: ReactNode;
  /** Below the product tiles (resuming a till pick). */
  finderBottom?: ReactNode;
  /** Under the cart heading (basket expiry at the till). */
  cartNotice?: ReactNode;
  /** After the cart lines. */
  afterLines?: ReactNode;
  /** Lines on the document when `afterLines` adds its own (free-text lines); defaults to the cart's. */
  lineCount?: number;
  /** After the notes: payment at the till, dates on quotes and invoices. */
  children?: ReactNode;
  /** `sales.price_override`: may sell off a SKU's sell multiple or minimum (sees a notice instead). */
  canBreakBatches?: boolean;
  /** The last save's `sale_quantity_rule` refusal, shown on each refused line until its quantity changes. */
  quantityRefusal?: QuantityRuleRefusal | null;
};

export function CartEditor(props: CartEditorProps) {
  const {
    mode, cart, preview, selectedCustomer, colleagues, customers, customerId,
  } = props;
  const [productQuery, setProductQuery] = useState("");
  const [productPage, setProductPage] = useState(1);
  const [productPageSize, setProductPageSize] = useState(12);
  const isTill = mode === "till";
  const lineCount = props.lineCount ?? cart.length;
  const documentWord = DOCUMENT[mode];

  // The browser never prices (ADR 0001): every amount on a cart line or in the summary is the server's.
  const showInclusive = preview?.prices_include_vat ?? true;
  const basis = showInclusive ? "incl. VAT" : "excl. VAT";
  const linePrices = alignPreviewLines(cart.map((line) => line.sku.id), preview);
  const money = (amount: string | number | undefined) =>
    amount === undefined ? (lineCount ? "—" : formatZarAmount("0.00")) : formatZarAmount(formatPriceAmount(Number(amount)));
  const beforeDiscount = preview
    ? Number(showInclusive ? preview.before_discount_inc_vat : preview.before_discount_ex_vat)
    : undefined;
  const discount = beforeDiscount === undefined || !preview
    ? undefined
    : beforeDiscount - Number(showInclusive ? preview.total_inc_vat : preview.subtotal_ex_vat);

  const blocked = (sku: Sku) => props.blockedReason?.(sku) ?? null;
  const comboOptions: SkuOption[] = props.products.map((sku) => {
    const reason = blocked(sku);
    return reason ? { ...sku, disabled: true, reason } : sku;
  });
  const selectedSku = props.products.find((sku) => sku.id === props.skuId);
  const selectedSkuOption = comboOptions.find((sku) => sku.id === props.skuId) ?? null;
  const numericQty = typeof props.qty === "number" ? props.qty : 0;
  // The finder and cart columns need 56rem; below that the SKU panel lies over the page.
  useWidePage();
  const canBreak = props.canBreakBatches ?? false;
  const finderBounds = selectedSku ? quantityInputBounds(selectedSku, canBreak) : { min: 1, step: 1 };
  const addValid =
    !props.searchDisabled &&
    !!selectedSku?.is_sellable &&
    !selectedSku.is_archived &&
    numericQty > 0 &&
    (props.canAddQty?.(selectedSku, numericQty) ?? true);

  const browserProducts = props.products.filter(
    (sku) =>
      filterSkuItem({ item: sku, inputValue: productQuery }) ||
      skuItemToString(sku).toLowerCase().includes(productQuery.toLowerCase()),
  );
  const browserPage = Math.min(
    productPage,
    Math.max(1, Math.ceil(browserProducts.length / productPageSize)),
  );
  const visibleProducts = browserProducts.slice(
    (browserPage - 1) * productPageSize,
    browserPage * productPageSize,
  );

  const colleague = colleagues?.find((item) => item.id === props.salesStaffId);

  function handleAddToCart() {
    if (!addValid || !selectedSku) return;
    if (props.onAdd(selectedSku, numericQty)) {
      props.onSkuIdChange("");
      props.onQtyChange(1);
    }
  }

  return (
    <div className={styles.layout}>
      <div className={`firstout-section-accent firstout-tone-info ${styles.productBrowser}`}>
        <Stack gap={5}>
          <Tile>
            <Stack gap={5}>
              <div className={styles.sectionHeading}>
                <div>
                  <p className="cds--type-label-01">{isTill ? "SHOWROOM PRODUCTS" : "PRODUCTS"}</p>
                  <h2 className="cds--type-heading-03">Find a product</h2>
                </div>
                <Tag type="blue">Retail incl. VAT</Tag>
              </div>
              {props.finderTop}

              <div className="firstout-till-picker-row">
                <ComboBox
                  id={`${mode}-sku`}
                  titleText="Find by product, SKU or barcode"
                  placeholder="Search by SKU, barcode, or name..."
                  items={comboOptions}
                  itemToString={skuItemToString}
                  itemToElement={(item) => item.reason ? (
                    <span className={styles.reserved}>
                      <Locked size={16} aria-hidden />
                      <span>{skuItemToString(item)} · {item.reason}</span>
                    </span>
                  ) : (
                    <span>
                      {skuItemToString(item)}
                      {props.stockState && (
                        <span className={styles.stockState}> · {props.stockState(item)}</span>
                      )}
                    </span>
                  )}
                  selectedItem={selectedSkuOption}
                  shouldFilterItem={filterSkuItem}
                  onChange={({ selectedItem }) => {
                    props.onSkuIdChange(selectedItem?.id ?? "");
                    // A batch-sold SKU starts at its minimum.
                    if (selectedItem) props.onQtyChange(startQty(selectedItem));
                  }}
                  disabled={props.searchDisabled}
                  onInputChange={(value) => {
                    setProductQuery(value);
                    setProductPage(1);
                  }}
                />
                {props.onBrowseCatalogue ? (
                  <Button kind="tertiary" onClick={props.onBrowseCatalogue}>
                    Browse Catalogue
                  </Button>
                ) : (
                  <Button kind="tertiary" href="/catalogue" target="_blank" rel="noopener">
                    Browse Catalogue
                  </Button>
                )}
              </div>

              <NumberInput
                id={`${mode}-qty`}
                label="Quantity"
                min={finderBounds.min}
                step={finderBounds.step}
                max={selectedSku ? props.qtyMax?.(selectedSku) : undefined}
                invalidText={selectedSku && typeof props.qty === "number" && props.qty < finderBounds.min
                  ? quantityRuleHelper(selectedSku) ?? undefined : undefined}
                value={props.qty}
                onChange={(_, { value }) => {
                  if (value === "") {
                    props.onQtyChange("");
                  } else {
                    props.onQtyChange(typeof value === "number" ? value : Number(value));
                  }
                }}
                helperText={
                  selectedSku && !props.searchDisabled
                    ? [quantityRuleHelper(selectedSku), props.stockState?.(selectedSku)].filter(Boolean).join(" · ") || undefined
                    : undefined
                }
                disabled={!props.skuId}
              />

              <Button kind="secondary" disabled={!addValid} onClick={handleAddToCart}>
                Add to cart
              </Button>
              <div className={styles.productGrid}>
                {visibleProducts.map((sku) => {
                  const reason = blocked(sku);
                  return (
                    <ClickableTile
                      role="button"
                      key={sku.id}
                      aria-label={`Add ${sku.name} to ${isTill ? "sale" : documentWord}${reason ? `. ${reason}` : ""}`}
                      onClick={() => props.onAdd(sku, startQty(sku))}
                      disabled={
                        props.addDisabled ||
                        (props.tileDisabled?.(sku) ?? false)
                      }
                    >
                      <div className={styles.productCard}>
                        <div className={styles.productPhoto}>
                          {sku.photo_storage_key ? (
                            <StaffImage src={skuPhotoUrl(sku.id)} alt="" className={styles.productImage} />
                          ) : (
                            <ImageIcon size={32} aria-hidden />
                          )}
                        </div>
                        <h3 className="cds--type-heading-compact-01">{sku.name}</h3>
                        <p className="cds--type-label-01">{sku.our_ref}</p>
                        <div className={styles.priceRow}>
                          {/* The shelf price as stored; the customer's own price shows on the cart line. */}
                          <p className="cds--type-body-01">
                            {Number(sku.retail_inc_vat ?? 0) > 0
                              ? `${formatZarAmount(sku.retail_inc_vat)} Retail`
                              : "No Retail price"}
                          </p>
                          <Purchase size={20} aria-hidden />
                        </div>
                        {reason ? (
                          <p className={`cds--type-label-01 ${styles.reserved}`}>
                            <Locked size={16} aria-hidden />
                            {reason}
                          </p>
                        ) : props.stockState ? (
                          <p className={`cds--type-label-01 ${styles.stockState}`}>
                            {props.stockState(sku)}
                          </p>
                        ) : null}
                      </div>
                    </ClickableTile>
                  );
                })}
              </div>
              {!browserProducts.length && (
                <div className={styles.empty}>
                  <h3 className="cds--type-heading-03">No matching products</h3>
                  <p className="cds--type-body-01">
                    {isTill
                      ? "Try another product name or SKU, or choose a showroom with available stock."
                      : "Try another product name or SKU."}
                  </p>
                </div>
              )}
              <Pagination
                page={browserPage}
                pageSize={productPageSize}
                pageSizes={[12, 24, 48]}
                totalItems={browserProducts.length}
                itemsPerPageText="Products per page:"
                backwardText="Previous page"
                forwardText="Next page"
                onChange={({ page, pageSize }) => {
                  setProductPage(page);
                  setProductPageSize(pageSize);
                }}
              />
              {props.finderBottom}
            </Stack>
          </Tile>
        </Stack>
      </div>

      <div className={`firstout-section-accent firstout-tone-info ${styles.sale}`}>
        <Tile>
          <Stack gap={5}>
            <div className={styles.sectionHeading}>
              <h2 className="cds--type-heading-03">{props.title ?? "Current sale"}</h2>
              <Tag type="gray">
                {lineCount} {props.lineCount === undefined ? "product " : ""}{lineCount === 1 ? "line" : "lines"}
              </Tag>
            </div>
            {props.cartNotice}
            <div className="firstout-till-picker-row">
              <CustomerPicker
                id={`${mode}-customer`}
                titleText={isTill ? "Customer (optional)" : "Customer"}
                customers={customers}
                selectedId={customerId}
                onChange={props.onCustomerChange}
              />
              {props.onAddCustomer ? (
                <Button
                  kind="ghost"
                  hasIconOnly
                  renderIcon={UserFollow}
                  iconDescription="Add customer"
                  onClick={props.onAddCustomer}
                />
              ) : (
                <Button
                  kind="ghost"
                  hasIconOnly
                  renderIcon={UserFollow}
                  iconDescription="Add customer (opens a new tab)"
                  href="/customers"
                  target="_blank"
                  rel="noopener"
                />
              )}
            </div>

            {preview && (
              <div>
                <p className="cds--type-label-01">Pricing for this {isTill ? "sale" : documentWord}</p>
                <p className="cds--type-body-01">
                  {preview.classification} · {preview.price_list_name ?? "Catalogue tier"} · Unit prices {basis}
                </p>
              </div>
            )}
            {colleagues?.length ? (
              <Select
                id={`${mode}-sales-colleague`}
                labelText="Sales colleague"
                value={colleague?.id ?? ""}
                invalid={lineCount > 0 && !colleague}
                invalidText={`Choose who made this ${isTill ? "sale" : documentWord}`}
                // Only once the server has priced every line; a partial sum would understate it.
                helperText={colleague && linePrices.every(Boolean) ? `Counts towards ${colleague.short_name || colleague.name.split(/\s+/)[0]}'s commission: ${zar(commissionBase(cart.map((line, index) => ({
                  excluded: !!line.sku.exclude_from_commission,
                  exVat: linePrices[index]?.ex_vat,
                }))))} excl. VAT` : undefined}
                onChange={(event) => {
                  props.onSalesStaffChange(event.target.value);
                  rememberColleague(event.target.value);
                }}
              >
                <SelectItem value="" text={`Who made this ${isTill ? "sale" : documentWord}?`} disabled />
                {colleagues.map((item) => (
                  <SelectItem key={item.id} value={item.id} text={item.name} />
                ))}
              </Select>
            ) : props.colleaguesError ? (
              <InlineNotification
                kind="warning"
                title="Sales colleagues could not be loaded"
                subtitle={`Reload the ${isTill ? "till" : "page"} to choose who made this ${isTill ? "sale" : documentWord}.`}
                hideCloseButton
                lowContrast
              />
            ) : null}

            {props.pricingError ? (
              <Stack gap={3}>
                <InlineNotification kind="error" title={`Could not confirm ${isTill ? "sale" : documentWord} prices`} subtitle={props.pricingError} lowContrast hideCloseButton />
                <div><Button kind="tertiary" size="sm" onClick={props.onRetryPricing}>Check prices again</Button></div>
              </Stack>
            ) : lineCount > 0 && !preview ? (
              <p role="status" className="cds--type-body-01">Checking {isTill ? "sale" : documentWord} prices…</p>
            ) : null}

            {selectedCustomer?.on_hold ? (
              <InlineNotification
                kind="warning"
                title="Customer is on hold"
                subtitle={
                  selectedCustomer.on_hold_reason ||
                  "This customer cannot be sold to until the hold is lifted."
                }
                hideCloseButton
                lowContrast
              />
            ) : null}

            <section
              aria-label={`Products in ${isTill ? "current sale" : `this ${documentWord}`}`}
              className={styles.cart}
            >
              {lineCount === 0 ? (
                <div className={styles.empty}>
                  <h3 className="cds--type-heading-compact-01">
                    {isTill ? "Start a new sale" : "No products yet"}
                  </h3>
                  <p className="cds--type-body-01">Choose a product to add it here.</p>
                </div>
              ) : (
                cart.map((line, index) => {
                  const linePricing = linePrices[index];
                  const lineDiscount = Number(linePricing?.discount_percent ?? 0);
                  const refused = blockedReason(linePricing?.blocked_by);
                  const quantityNotice = lineQuantityNotice(linePricing, props.quantityRefusal, line.sku.id, line.qty);
                  const lineBounds = quantityInputBounds(line.sku, canBreak);
                  const lineQtyMax = props.lineQtyMax?.(line.sku);
                  return (
                    <div className={styles.cartLine} key={line.key}>
                      <div className={styles.cartProduct}>
                        <SkuThumb sku={line.sku} />
                        <div>
                          <h3 className="cds--type-heading-compact-01">{line.sku.name}</h3>
                          <SkuLink
                            id={line.sku.id}
                            context={{ ids: cart.map((item) => item.sku.id), label: isTill ? "Sale" : documentWord }}
                            className="cds--link cds--type-label-01"
                          >
                            {line.sku.our_ref}
                          </SkuLink>
                          {props.lineNote?.(line)}
                        </div>
                        <Button
                          kind="ghost"
                          size="sm"
                          hasIconOnly
                          renderIcon={TrashCan}
                          iconDescription={`Remove ${line.sku.name}`}
                          onClick={() => props.onRemoveLine(line.key)}
                        />
                      </div>
                      {isTill && line.sku.is_archived && (
                        <p className="cds--type-label-01">
                          Archived kit: locked to its original pick
                          quantity. Remove the line to cancel this checkout.
                        </p>
                      )}
                      {!line.sku.is_sellable && (
                        <InlineNotification
                          kind="warning"
                          title="Not for sale"
                          subtitle={`Remove this item to complete the ${isTill ? "sale" : documentWord}.`}
                          lowContrast
                          hideCloseButton
                        />
                      )}
                      <div className={styles.cartControls}>
                        <NumberInput
                          id={`cart-qty-${line.key}`}
                          disabled={line.sku.is_archived}
                          label="Quantity"
                          size="sm"
                          min={lineBounds.min}
                          step={lineBounds.step}
                          max={lineQtyMax || undefined}
                          helperText={quantityRuleHelper(line.sku) ?? undefined}
                          // Carbon swaps the helper for this when the value is off its own min/step, so the rule stays in view.
                          invalidText={line.qty < lineBounds.min ? quantityRuleHelper(line.sku) ?? undefined : undefined}
                          value={line.qty}
                          onChange={(_, { value }) => {
                            const next =
                              value === "" ? 1 : typeof value === "number" ? value : Number(value);
                            props.onUpdateLine(line.key, { qty: Math.max(1, next) });
                          }}
                        />
                        {/* Without till.discount a carried-over discount can only be lowered or cleared. */}
                        {(props.canDiscount || line.discountPercent > 0) && (
                          <NumberInput
                            id={`cart-discount-${line.key}`}
                            label="Discount (%)"
                            size="sm"
                            min={0}
                            max={props.canDiscount ? 100 : line.discountPercent}
                            value={line.discountPercent}
                            onChange={(_, { value }) => {
                              const next =
                                value === "" ? 0 : typeof value === "number" ? value : Number(value);
                              props.onUpdateLine(line.key, { discountPercent: clampDiscount(next) });
                            }}
                          />
                        )}
                      </div>
                      <div className={styles.priceRow}>
                        {/* The list unit and the discount %, never a discounted unit (ADR 0001). */}
                        <p className="cds--type-label-01">Unit ({basis})</p>
                        <p className="cds--type-body-01">
                          {money(showInclusive ? linePricing?.unit_inc_vat : linePricing?.unit_ex_vat)}
                          {lineDiscount > 0 ? ` · ${lineDiscount}% off` : ""}
                        </p>
                      </div>
                      <div className={styles.priceRow}>
                        <p className="cds--type-label-01">Line total incl. VAT</p>
                        <p className="cds--type-heading-compact-01">{money(linePricing?.inc_vat)}</p>
                      </div>
                      {linePricing?.price_warning && (
                        <InlineNotification
                          kind="warning"
                          lowContrast
                          hideCloseButton
                          title="Price list or tier fallback"
                          subtitle={linePricing.price_warning}
                        />
                      )}
                      {linePricing?.suspect_price_warning && (
                        <InlineNotification
                          kind="warning"
                          lowContrast
                          hideCloseButton
                          title="Check this price"
                          subtitle={linePricing.suspect_price_warning}
                        />
                      )}
                      {quantityNotice && (
                        <InlineNotification
                          kind={quantityNotice.kind === "error" ? "error" : "info"}
                          lowContrast
                          hideCloseButton
                          title={quantityNotice.kind === "error"
                            ? "Change the quantity"
                            : "You're breaking a batch"}
                          subtitle={quantityNotice.kind === "error"
                            ? quantityNotice.message
                            : `${quantityNotice.message} You can sell this quantity because you may override prices.`}
                        />
                      )}
                      {refused && (
                        <InlineNotification
                          kind="error"
                          lowContrast
                          hideCloseButton
                          title={`This ${isTill ? "sale" : documentWord} can't be saved with this line`}
                          subtitle={refused}
                        />
                      )}
                    </div>
                  );
                })
              )}
              {props.afterLines}
            </section>
            <h3 className="cds--type-heading-compact-01">
              {mode === "quote" ? "Quote summary" : "Sale summary"}
            </h3>

            <dl className="firstout-sale-summary">
              <div className="firstout-sale-summary__row">
                <dt>{showInclusive ? "Subtotal (before discount, incl. VAT)" : "Subtotal (before discount, excl. VAT)"}</dt>
                <dd>{money(beforeDiscount)}</dd>
              </div>
              <div className="firstout-sale-summary__row firstout-sale-summary__row--discount">
                <dt>{showInclusive ? "Line discounts" : "Line discounts excl. VAT"}</dt>
                <dd>{discount && discount > 0 ? "- " : ""}{money(discount)}</dd>
              </div>
              {!showInclusive && (
                <div className="firstout-sale-summary__row">
                  <dt>Subtotal after discount excl. VAT</dt>
                  <dd>{money(preview?.subtotal_ex_vat)}</dd>
                </div>
              )}
              <div className="firstout-sale-summary__row">
                <dt>VAT{preview ? ` (${vatPercentLabel(preview.vat_rate)})` : ""}{showInclusive ? " included" : ""}</dt>
                <dd>{money(preview?.vat_amount)}</dd>
              </div>
              <div className="firstout-sale-summary__row firstout-sale-summary__row--total">
                <dt>Total incl. VAT</dt>
                <dd>{money(preview?.total_inc_vat)}</dd>
              </div>
            </dl>

            <TextArea
              id={`${mode}-note-printed`}
              labelText={`Note on ${documentWord}`}
              helperText={`Printed on the ${documentWord} the customer receives.`}
              rows={2}
              maxCount={INVOICE_NOTE_MAX}
              enableCounter
              value={props.notePrinted}
              onChange={(event) => props.onNotePrintedChange(event.target.value)}
            />
            <TextArea
              id={`${mode}-note-internal`}
              labelText="Internal note"
              helperText="Staff only. Never printed."
              rows={2}
              maxCount={INVOICE_NOTE_MAX}
              enableCounter
              value={props.noteInternal}
              onChange={(event) => props.onNoteInternalChange(event.target.value)}
            />

            {props.children}
          </Stack>
        </Tile>
      </div>
    </div>
  );
}
