"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Add, TrashCan } from "@carbon/icons-react";
import {
  Button,
  Checkbox,
  ComboBox,
  Dropdown,
  IconButton,
  InlineNotification,
  Modal,
  NumberInput,
  ProgressIndicator,
  ProgressStep,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextArea,
  TextInput,
  Tile,
} from "@carbon/react";

import { LoadingField, LoadingRegion } from "@/components/page-loading";
import {
  createPurchaseOrder,
  listProformas,
  listSkus,
  listSuppliers,
  type Proforma,
  type PurchaseOrder,
  type Sku,
  type Supplier,
} from "@/lib/api";
import {
  changeSupplierCodeSku,
  displayFabric,
  editSupplierCode,
  prefillSupplierCode,
} from "@/lib/po-supplier-code";
import {
  createOrderPayload,
  factoryTotal,
  formatFactoryAmount,
  lineFieldId,
  MAX_ORDER_QUANTITY,
  newOrderDraft,
  newOrderLine,
  orderRequiresApproval,
  prefilledOrderDraft,
  validateOrderDraft,
  type FormErrors,
  type OrderDraft,
  type OrderLine,
} from "./composer-state";
import styles from "./purchase-orders.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (order: PurchaseOrder) => void;
  /** Start with this SKU on one line and its preferred supplier chosen (`?prefill_sku=` on the page). */
  prefillSkuId?: string | null;
};
type Choices = { suppliers: Supplier[]; proformas: Proforma[]; skus: Sku[] };
const steps = ["Supplier & reference", "Order lines", "Review"];
const skuLabel = (sku: Sku | null) =>
  sku ? `${sku.our_ref} · ${sku.name}` : "";
function focusField(id: string) {
  requestAnimationFrame(() => {
    const root = document.getElementById(id);
    const field = root?.matches("input,button,textarea,[tabindex]")
      ? root
      : root?.querySelector<HTMLElement>("input,button,[tabindex]");
    (field || document.getElementById("po-create-step-heading"))?.focus();
  });
}

/** Unmount on close: another order always starts with a clean draft and fresh choices. */
export function PurchaseOrderComposer(props: Props) {
  return props.open ? (
    <ComposerSession onClose={props.onClose} onCreated={props.onCreated} prefillSkuId={props.prefillSkuId} />
  ) : null;
}

function ComposerSession({ onClose, onCreated, prefillSkuId }: Omit<Props, "open">) {
  const [draft, setDraft] = useState<OrderDraft>(newOrderDraft);
  const choicesQuery = useQuery({
    queryKey: ["purchase-orders", "composer-choices"],
    queryFn: async (): Promise<Choices> => {
      const [suppliers, proformas, skus] = await Promise.all([
        listSuppliers({ archived: false }),
        listProformas(),
        listSkus({ lifecycle: "active" }),
      ]);
      return {
        suppliers: suppliers.filter((item) => !item.is_archived),
        proformas: proformas.filter((item) => !item.is_archived),
        skus: skus.filter((item) => !item.is_archived),
      };
    },
  });
  const choices = choicesQuery.data ?? null;
  // Apply the prefilled SKU once, as soon as the choices it needs have loaded.
  const [prefill, setPrefill] = useState<"pending" | "applied" | "missing">(prefillSkuId ? "pending" : "applied");
  if (prefill === "pending" && choices) {
    const sku = choices.skus.find((item) => item.id === prefillSkuId);
    setPrefill(sku ? "applied" : "missing");
    if (sku) setDraft(prefilledOrderDraft(sku, choices.suppliers));
  }
  // Every open shows its own load, as when choices were fetched per session.
  const loading = choicesQuery.isFetching;
  const loadError =
    choicesQuery.error && !loading
      ? choicesQuery.error.message || "Could not load suppliers and products."
      : null;
  const [serverError, setServerError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<FormErrors>({});
  const [dirty, setDirty] = useState(false);
  const [discard, setDiscard] = useState(false);
  const [saving, setSaving] = useState(false);
  const busy = useRef(false);
  const closeState = useRef({ dirty, discard, onClose });

  useLayoutEffect(() => {
    closeState.current = { dirty, discard, onClose };
  }, [dirty, discard, onClose]);

  useEffect(() => {
    if (!discard) return;
    const frame = requestAnimationFrame(() =>
      document
        .querySelector<HTMLElement>('#po-create-dialog [role="dialog"]')
        ?.focus(),
    );
    return () => cancelAnimationFrame(frame);
  }, [discard]);

  const setLines = useCallback(
    (update: (lines: OrderLine[]) => OrderLine[]) => {
      setDraft((current) => ({ ...current, lines: update(current.lines) }));
    },
    [],
  );
  // The prefilled line's supplier code, looked up once like a chosen SKU's.
  const prefillCodeRequested = useRef(false);
  useEffect(() => {
    if (prefill !== "applied" || !prefillSkuId || prefillCodeRequested.current) return;
    prefillCodeRequested.current = true;
    const line = draft.lines[0];
    const sku = choices?.skus.find((item) => item.id === prefillSkuId);
    if (sku && line?.sku_id === sku.id && draft.supplier_id)
      void prefillSupplierCode(setLines, line.key, draft.supplier_id, sku);
  }, [prefill, prefillSkuId, choices, draft, setLines]);
  const supplier = choices?.suppliers.find(
    (item) => item.id === draft.supplier_id,
  );
  const currency = supplier ? supplier.default_currency || "USD" : null;
  const proforma = choices?.proformas.find(
    (item) => item.id === draft.proforma_id,
  );
  const unlinked = draft.lines.filter((line) => !line.sku_id).length;
  const total = factoryTotal(draft.lines);
  const requiresApproval = orderRequiresApproval(draft);
  function patch(patch: Partial<OrderDraft>) {
    setDirty(true);
    setDraft((current) => ({ ...current, ...patch }));
  }
  function updateLine(key: string, patch: Partial<OrderLine>) {
    setDirty(true);
    setLines((lines) =>
      lines.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }
  function changeSupplier(next: Supplier | null | undefined) {
    const id = next?.id || "";
    if (id === draft.supplier_id) return;
    setDirty(true);
    setDraft((current) => ({
      ...current,
      supplier_id: id,
      proforma_id: "",
      lines: current.lines.map((line) => ({
        ...line,
        factory_unit_amount: "",
        supplier_code: line.supplierCodeTouched ? line.supplier_code : "",
        supplierCodeLookup: undefined,
      })),
    }));
    if (id)
      for (const line of draft.lines) {
        const sku = choices?.skus.find((item) => item.id === line.sku_id);
        if (sku && !line.supplierCodeTouched)
          void prefillSupplierCode(setLines, line.key, id, sku);
      }
  }
  function chooseSku(line: OrderLine, sku: Sku | null | undefined) {
    const id = sku?.id || "";
    if (id === line.sku_id) return;
    setDirty(true);
    setLines((current) =>
      current.map((item) =>
        item.key === line.key
          ? { ...changeSupplierCodeSku(item, id), factory_unit_amount: "" }
          : item,
      ),
    );
    if (sku && draft.supplier_id)
      void prefillSupplierCode(setLines, line.key, draft.supplier_id, sku);
  }
  // Carbon's document Escape listener retains the callback from when it opens.
  const requestClose = useCallback(() => {
    if (busy.current) return;
    const current = closeState.current;
    if (current.discard) {
      setDiscard(false);
      focusField("po-create-step-heading");
    } else if (current.dirty) setDiscard(true);
    else current.onClose();
  }, []);
  function back() {
    if (busy.current) return;
    if (discard) {
      setDiscard(false);
      focusField("po-create-step-heading");
    } else if (step > 0) {
      setStep(step - 1);
      setErrors({});
      focusField("po-create-step-heading");
    } else requestClose();
  }
  async function submit() {
    if (busy.current) return;
    if (discard) {
      onClose();
      return;
    }
    if (!choices || loading || loadError) return;
    const nextErrors = validateOrderDraft(draft, choices, step > 0);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      focusField(Object.keys(nextErrors)[0]);
      return;
    }
    if (step < 2) {
      setStep(step + 1);
      focusField("po-create-step-heading");
      return;
    }
    busy.current = true;
    setSaving(true);
    setServerError(null);
    let created: PurchaseOrder;
    try {
      created = await createPurchaseOrder(createOrderPayload(draft));
    } catch (error) {
      setServerError(
        error instanceof Error
          ? error.message
          : "Could not create the purchase order. Your details have been kept.",
      );
      focusField("po-create-server-error");
      busy.current = false;
      setSaving(false);
      return;
    }
    // A URL-opened composer may remain mounted until router.replace settles.
    // Keep a successful request locked throughout that closing interval.
    onCreated(created);
    onClose();
  }

  return (
    <Modal
      id="po-create-dialog"
      open
      size="lg"
      modalHeading={
        discard ? "Discard this purchase order?" : "New purchase order"
      }
      modalLabel={discard ? "UNSAVED CHANGES" : `STEP ${step + 1} OF 3`}
      primaryButtonText={
        discard
          ? "Discard changes"
          : saving
            ? "Creating…"
            : step < 2
              ? "Continue"
              : "Create purchase order"
      }
      secondaryButtonText={
        discard ? "Keep editing" : step > 0 ? "Back" : "Cancel"
      }
      primaryButtonDisabled={
        saving || (!discard && (loading || !!loadError || !choices))
      }
      danger={discard}
      onRequestClose={requestClose}
      onSecondarySubmit={back}
      onRequestSubmit={() => void submit()}
      preventCloseOnClickOutside
      selectorPrimaryFocus="#po-create-step-heading"
    >
      {discard ? (
        <p className="cds--type-body-01">
          Your supplier details, order lines and notes will be cleared. No
          purchase order has been created.
        </p>
      ) : (
        <div className={styles.stack}>
          <ProgressIndicator
            currentIndex={step}
            spaceEqually
            onChange={(index) => {
              if (index < step && !saving) {
                setStep(index);
                setErrors({});
                focusField("po-create-step-heading");
              }
            }}
          >
            {steps.map((label, index) => (
              <ProgressStep
                key={label}
                label={label}
                complete={index < step}
                disabled={saving || index > step}
                description={label}
              />
            ))}
          </ProgressIndicator>
          <div className={styles.between}>
            <h2
              id="po-create-step-heading"
              tabIndex={-1}
              className="cds--type-heading-03"
            >
              {steps[step]}
            </h2>
            {step > 0 && (
              <Button
                kind="ghost"
                size="sm"
                disabled={saving}
                onClick={requestClose}
              >
                Cancel order
              </Button>
            )}
          </div>
          {loadError && (
            <div className={styles.stack}>
              <InlineNotification
                lowContrast
                kind="error"
                title="Order form unavailable"
                subtitle={loadError}
                hideCloseButton
              />
              <Button
                kind="tertiary"
                onClick={() => void choicesQuery.refetch()}
              >
                Try again
              </Button>
            </div>
          )}
          {prefill === "missing" && (
            <InlineNotification
              lowContrast
              kind="warning"
              title="That SKU can't be ordered"
              subtitle="It is archived or no longer exists. Choose a product on the order lines."
              hideCloseButton
            />
          )}
          {serverError && (
            <div id="po-create-server-error" tabIndex={-1}>
              <InlineNotification
                lowContrast
                kind="error"
                title="Could not create purchase order"
                subtitle={serverError}
                hideCloseButton
              />
            </div>
          )}
          {!!Object.keys(errors).length && (
            <InlineNotification
              lowContrast
              kind="error"
              title="Check the highlighted fields"
              subtitle="Complete the required information before continuing."
              hideCloseButton
            />
          )}
          {loading ? (
            <LoadingRegion label="Loading supplier choices…">
              <div className={styles.stack}>
                <p className="cds--type-body-01">
                  Choose who you are ordering from. The supplier determines the factory currency.
                </p>
                <div className={styles.twoColumns}>
                  <LoadingField label="Supplier (required)" />
                  <LoadingField label="Factory currency" helperText="From the supplier’s default currency." />
                  <LoadingField label="Supplier reference (optional)" helperText="The supplier’s reference. Your PO number is assigned on creation." />
                  <LoadingField label="Linked proforma (optional)" helperText="Only this supplier’s active proformas are available." />
                </div>
                <TextArea id="loading-po-notes" labelText="Order notes (optional)" rows={3} disabled />
                <Checkbox id="loading-po-approval" labelText="Submit for owner approval" disabled />
              </div>
            </LoadingRegion>
          ) : (
            choices &&
            !loadError && (
              <fieldset disabled={saving} className={styles.form}>
                {step === 0 && (
                  <div className={styles.stack}>
                    <p className="cds--type-body-01">
                      Choose who you are ordering from. The supplier determines
                      the factory currency.
                    </p>
                    <div className={styles.twoColumns}>
                      <Dropdown
                        id="po-supplier"
                        titleText="Supplier (required)"
                        label="Choose a supplier"
                        items={choices.suppliers}
                        itemToString={(item) => item?.name || ""}
                        selectedItem={supplier || null}
                        onChange={({ selectedItem }) =>
                          changeSupplier(selectedItem)
                        }
                        invalid={!!errors["po-supplier"]}
                        invalidText={errors["po-supplier"]}
                      />
                      <TextInput
                        id="po-factory-currency"
                        labelText="Factory currency"
                        value={currency || "Select a supplier first"}
                        readOnly
                        helperText="From the supplier’s default currency."
                      />
                      <TextInput
                        id="po-supplier-ref"
                        labelText="Supplier reference (optional)"
                        maxLength={128}
                        value={draft.supplier_ref}
                        onChange={(event) =>
                          patch({ supplier_ref: event.target.value })
                        }
                        helperText="The supplier’s reference. Your PO number is assigned on creation."
                        invalid={!!errors["po-supplier-ref"]}
                        invalidText={errors["po-supplier-ref"]}
                      />
                      <Dropdown
                        id="po-proforma"
                        titleText="Linked proforma (optional)"
                        label="No linked proforma"
                        disabled={!supplier}
                        items={choices.proformas.filter(
                          (item) => item.supplier_id === draft.supplier_id,
                        )}
                        itemToString={(item) =>
                          item
                            ? `${item.invoice_number} (${item.invoice_date})`
                            : ""
                        }
                        selectedItem={proforma || null}
                        onChange={({ selectedItem }) =>
                          patch({ proforma_id: selectedItem?.id || "" })
                        }
                        helperText="Only this supplier’s active proformas are available."
                        invalid={!!errors["po-proforma"]}
                        invalidText={errors["po-proforma"]}
                      />
                    </div>
                    {draft.proforma_id && (
                      <Button
                        kind="ghost"
                        size="sm"
                        onClick={() => patch({ proforma_id: "" })}
                      >
                        Remove linked proforma
                      </Button>
                    )}
                    <TextArea
                      id="po-notes"
                      labelText="Order notes (optional)"
                      rows={3}
                      value={draft.notes}
                      onChange={(event) => patch({ notes: event.target.value })}
                    />
                    <Checkbox
                      id="po-submit-for-approval"
                      labelText="Submit for owner approval"
                      checked={draft.submit_for_approval}
                      onChange={(_, data) =>
                        patch({ submit_for_approval: data.checked })
                      }
                    />
                    <p className="cds--type-helper-text-01">
                      Description-only lines also require approval. The server
                      checks your business’s approval policy when the order is
                      created.
                    </p>
                  </div>
                )}
                {step === 1 && (
                  <div className={styles.stack}>
                    <div className={styles.between}>
                      <p className="cds--type-body-01">
                        {supplier?.name} · Factory currency{" "}
                        <strong>{currency}</strong>
                      </p>
                      <Tag type="gray">
                        {draft.lines.length} order{" "}
                        {draft.lines.length === 1 ? "line" : "lines"}
                      </Tag>
                    </div>
                    <p className="cds--type-body-01">
                      Choose an existing SKU, or describe an item to link later.
                      Changing the supplier or SKU clears factory amounts so
                      costs are checked again.
                    </p>
                    {draft.lines.map((line, index) => {
                      const sku = choices.skus.find(
                        (item) => item.id === line.sku_id,
                      );
                      const fabric = displayFabric(sku?.fabric);
                      return (
                        <Tile key={line.key}>
                          <div className={styles.stack}>
                            <div className={styles.between}>
                              <h3 className="cds--type-heading-compact-01">
                                Line {index + 1}
                              </h3>
                              <IconButton
                                kind="ghost"
                                size="sm"
                                label={`Remove line ${index + 1}`}
                                disabled={draft.lines.length === 1}
                                onClick={() => {
                                  setDirty(true);
                                  setLines((current) =>
                                    current.filter(
                                      (item) => item.key !== line.key,
                                    ),
                                  );
                                }}
                              >
                                <TrashCan />
                              </IconButton>
                            </div>
                            <div className={styles.twoColumns}>
                              <ComboBox
                                id={lineFieldId(line, "sku")}
                                titleText="Product / SKU (optional)"
                                placeholder="Search SKU or product name"
                                items={choices.skus}
                                itemToString={skuLabel}
                                selectedItem={sku || null}
                                shouldFilterItem={({ item, inputValue }) =>
                                  skuLabel(item)
                                    .toLowerCase()
                                    .includes((inputValue || "").toLowerCase())
                                }
                                onChange={({ selectedItem }) =>
                                  chooseSku(line, selectedItem)
                                }
                                invalid={!!errors[lineFieldId(line, "sku")]}
                                invalidText={errors[lineFieldId(line, "sku")]}
                                helperText={
                                  fabric
                                    ? `Finish: ${fabric}`
                                    : "No SKU? Enter a description below."
                                }
                              />
                              <TextInput
                                id={lineFieldId(line, "code")}
                                labelText="Supplier code (optional)"
                                maxLength={128}
                                value={line.supplier_code}
                                onChange={(event) => {
                                  setDirty(true);
                                  setLines((current) =>
                                    current.map((item) =>
                                      item.key === line.key
                                        ? editSupplierCode(
                                            item,
                                            event.target.value,
                                          )
                                        : item,
                                    ),
                                  );
                                }}
                                helperText={
                                  line.supplierCodeLookup?.status === "loading"
                                    ? "Checking supplier code…"
                                    : "Prefilled for this supplier and SKU; manual entries are preserved."
                                }
                                invalid={
                                  !!errors[lineFieldId(line, "code")] ||
                                  line.supplierCodeLookup?.status === "error"
                                }
                                invalidText={
                                  line.supplierCodeLookup?.error ||
                                  errors[lineFieldId(line, "code")]
                                }
                              />
                            </div>
                            {line.supplierCodeLookup?.status === "error" &&
                              sku && (
                                <Button
                                  kind="ghost"
                                  size="sm"
                                  onClick={() =>
                                    void prefillSupplierCode(
                                      setLines,
                                      line.key,
                                      draft.supplier_id,
                                      sku,
                                    )
                                  }
                                >
                                  Retry supplier code
                                </Button>
                              )}
                            <TextInput
                              id={lineFieldId(line, "description")}
                              labelText={
                                sku
                                  ? "Line description (optional)"
                                  : "Item description (required without a SKU)"
                              }
                              value={line.description}
                              maxLength={512}
                              placeholder={sku?.name}
                              onChange={(event) =>
                                updateLine(line.key, {
                                  description: event.target.value,
                                })
                              }
                              invalid={
                                !!errors[lineFieldId(line, "description")]
                              }
                              invalidText={
                                errors[lineFieldId(line, "description")]
                              }
                            />
                            <div className={styles.threeColumns}>
                              <NumberInput
                                id={lineFieldId(line, "qty")}
                                label="Quantity (required)"
                                min={1}
                                max={MAX_ORDER_QUANTITY}
                                step={1}
                                value={line.qty}
                                allowEmpty
                                onChange={(_, data) =>
                                  updateLine(line.key, {
                                    qty:
                                      data.value === ""
                                        ? ""
                                        : Number(data.value),
                                  })
                                }
                                invalid={!!errors[lineFieldId(line, "qty")]}
                                invalidText={
                                  errors[lineFieldId(line, "qty")] ||
                                  "Enter a whole number from 1 to 9,999,999,999."
                                }
                              />
                              <TextInput
                                id={lineFieldId(line, "factory")}
                                labelText={`Factory unit amount (${currency}, required)`}
                                value={line.factory_unit_amount}
                                inputMode="decimal"
                                onChange={(event) =>
                                  updateLine(line.key, {
                                    factory_unit_amount: event.target.value,
                                  })
                                }
                                invalid={!!errors[lineFieldId(line, "factory")]}
                                invalidText={
                                  errors[lineFieldId(line, "factory")]
                                }
                                helperText="Supplier cost, up to 4 decimal places. Not the retail selling price."
                              />
                              <div className={styles.smallStack}>
                                <p className="cds--type-label-01">
                                  Factory line total
                                </p>
                                <p className="cds--type-heading-03">
                                  {formatFactoryAmount(
                                    factoryTotal([line]),
                                    currency,
                                  )}
                                </p>
                              </div>
                            </div>
                            <TextInput
                              id={lineFieldId(line, "notes")}
                              labelText="Line note (optional)"
                              value={line.notes}
                              onChange={(event) =>
                                updateLine(line.key, {
                                  notes: event.target.value,
                                })
                              }
                            />
                            {!sku && (
                              <p className="cds--type-helper-text-01">
                                This description-only line requires a SKU before
                                the order can be approved or processed.
                              </p>
                            )}
                          </div>
                        </Tile>
                      );
                    })}
                    <div className={styles.between}>
                      <Button
                        kind="tertiary"
                        renderIcon={Add}
                        onClick={() => {
                          setDirty(true);
                          setLines((current) => [...current, newOrderLine()]);
                        }}
                      >
                        Add order line
                      </Button>
                      <p className="cds--type-heading-03">
                        Factory total: {formatFactoryAmount(total, currency)}
                      </p>
                    </div>
                  </div>
                )}
                {step === 2 && (
                  <div className={styles.stack}>
                    <Tile>
                      <div className={styles.twoColumns}>
                        <div className={styles.smallStack}>
                          <p className="cds--type-label-01">Supplier</p>
                          <p className="cds--type-heading-compact-01">
                            {supplier?.name}
                          </p>
                          <p className="cds--type-body-01">
                            Factory currency: {currency}
                          </p>
                        </div>
                        <div className={styles.smallStack}>
                          <p className="cds--type-label-01">References</p>
                          <p className="cds--type-body-01">
                            Supplier:{" "}
                            {draft.supplier_ref.trim() || "Not provided"}
                          </p>
                          <p className="cds--type-body-01">
                            Proforma: {proforma?.invoice_number || "Not linked"}
                          </p>
                        </div>
                      </div>
                    </Tile>
                    <TableContainer
                      title="Order lines"
                      description="Factory amounts in the supplier’s currency"
                    >
                      <div className={styles.tableScroll}>
                        <Table aria-label="Review purchase order lines">
                          <TableHead>
                            <TableRow>
                              <TableHeader>Item</TableHeader>
                              <TableHeader>Supplier code</TableHeader>
                              <TableHeader className={styles.numeric}>
                                Qty
                              </TableHeader>
                              <TableHeader className={styles.numeric}>
                                Unit amount
                              </TableHeader>
                              <TableHeader className={styles.numeric}>
                                Line total
                              </TableHeader>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {draft.lines.map((line) => {
                              const sku = choices.skus.find(
                                (item) => item.id === line.sku_id,
                              );
                              return (
                                <TableRow key={line.key}>
                                  <TableCell>
                                    <p className="cds--type-body-01">
                                      {sku
                                        ? `${sku.our_ref} · ${sku.name}`
                                        : line.description}
                                    </p>
                                    {sku && displayFabric(sku.fabric) && (
                                      <p className="cds--type-label-01">
                                        {displayFabric(sku.fabric)}
                                      </p>
                                    )}
                                    {!sku && (
                                      <Tag type="warm-gray">Needs SKU</Tag>
                                    )}
                                    {sku && line.description && (
                                      <p className="cds--type-label-01">
                                        {line.description}
                                      </p>
                                    )}
                                    {line.notes && (
                                      <p className="cds--type-label-01">
                                        Note: {line.notes}
                                      </p>
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {line.supplier_code || "—"}
                                  </TableCell>
                                  <TableCell className={styles.numeric}>
                                    {line.qty}
                                  </TableCell>
                                  <TableCell className={styles.numeric}>
                                    {formatFactoryAmount(
                                      line.factory_unit_amount,
                                      currency,
                                    )}
                                  </TableCell>
                                  <TableCell className={styles.numeric}>
                                    {formatFactoryAmount(
                                      factoryTotal([line]),
                                      currency,
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    </TableContainer>
                    <div className={styles.between}>
                      <p className="cds--type-body-01">
                        {draft.lines.length}{" "}
                        {draft.lines.length === 1 ? "line" : "lines"} ·{" "}
                        {draft.lines.reduce(
                          (sum, line) => sum + Number(line.qty),
                          0,
                        )}{" "}
                        units
                      </p>
                      <p className="cds--type-heading-03">
                        Factory total: {formatFactoryAmount(total, currency)}
                      </p>
                    </div>
                    {draft.notes.trim() && (
                      <div className={styles.smallStack}>
                        <h3 className="cds--type-heading-compact-01">
                          Order notes
                        </h3>
                        <p className={`cds--type-body-01 ${styles.note}`}>
                          {draft.notes}
                        </p>
                      </div>
                    )}
                    <InlineNotification
                      lowContrast
                      hideCloseButton
                      kind={unlinked ? "warning" : "info"}
                      title={
                        requiresApproval
                          ? "Pending approval"
                          : "Ready to create"
                      }
                      subtitle={
                        unlinked
                          ? `${unlinked} description-only ${unlinked === 1 ? "line needs" : "lines need"} a SKU. The order remains pending until all SKUs are linked and an owner approves it.`
                          : draft.submit_for_approval
                            ? "You chose to submit this order for owner approval."
                            : "The server checks permissions, exchange rates and your business’s approval threshold when this order is created."
                      }
                    />
                    <p className="cds--type-helper-text-01">
                      Factory amounts only. Freight, clearance, exchange rates
                      and landed costs are recorded later. No retail VAT
                      calculation is applied here.
                    </p>
                  </div>
                )}
              </fieldset>
            )
          )}
        </div>
      )}
    </Modal>
  );
}
