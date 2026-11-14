"use client";

import { Catalog, Information } from "@carbon/icons-react";
import {
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tag,
  TextInput,
} from "@carbon/react";
import { useRef, useState } from "react";

import { formatZarAmount, updateSku, type Sku, type Supplier } from "@/lib/api";
import {
  buildCatalogueUpdate,
  catalogueFormFromSku,
  catalogueSaveFailure,
  CATALOGUE_FIELD_TABS,
  CATALOGUE_PRICE_FIELDS,
  firstCatalogueError,
  validateCatalogueForm,
  type CatalogueEditorErrors,
  type CatalogueEditorField,
} from "@/lib/catalogue-editor";

import styles from "./catalogue-sku-editor.module.css";

type CatalogueSkuEditorProps = {
  sku: Sku;
  suppliers: Supplier[];
  categories: string[];
  /** Undefined: no cost permission; null: cost unavailable. */
  unitCost: string | null | undefined;
  costLoading?: boolean;
  onClose: () => void;
  onSaved: (sku: Sku) => void;
};

const priceLabels = {
  stockist_inc_vat: "Stockist price",
  wholesale_inc_vat: "Wholesale price",
  decorator_inc_vat: "Decorator price",
  retail_inc_vat: "Retail price",
};

/** Mount with key={sku.id}; the form remains intact after any failed PATCH. */
export function CatalogueSkuEditor({
  sku,
  suppliers,
  categories,
  unitCost,
  costLoading = false,
  onClose,
  onSaved,
}: CatalogueSkuEditorProps) {
  const [form, setForm] = useState(() => catalogueFormFromSku(sku));
  const [tab, setTab] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [serverErrors, setServerErrors] = useState<CatalogueEditorErrors>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const payload = buildCatalogueUpdate(sku, form);
  const dirty = Object.keys(payload).length > 0;
  const errors = {
    ...(submitted ? validateCatalogueForm(form) : {}),
    ...serverErrors,
  };
  const categoryOptions = [
    ...new Set([...(sku.category ? [sku.category] : []), ...categories]),
  ].sort();
  const supplierName =
    suppliers.find((supplier) => supplier.id === form.preferred_supplier_id)
      ?.name ??
    (form.preferred_supplier_id === sku.preferred_supplier_id
      ? sku.preferred_supplier_name
      : null);

  function update(field: CatalogueEditorField, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setServerErrors((current) => ({ ...current, [field]: undefined }));
    setFailure(null);
  }

  function focusError(fields: CatalogueEditorErrors) {
    const first = firstCatalogueError(fields);
    if (!first) return;
    setTab(CATALOGUE_FIELD_TABS[first]);
    requestAnimationFrame(() =>
      document.getElementById(`catalogue-edit-${first}`)?.focus(),
    );
  }

  function requestClose() {
    if (savingRef.current) return;
    if (discardOpen) setDiscardOpen(false);
    else if (dirty) setDiscardOpen(true);
    else onClose();
  }

  async function save() {
    if (savingRef.current) return;
    if (discardOpen) {
      onClose();
      return;
    }
    const validation = validateCatalogueForm(form);
    setSubmitted(true);
    setServerErrors({});
    setFailure(null);
    if (firstCatalogueError(validation)) {
      focusError(validation);
      return;
    }
    if (!dirty) return;
    savingRef.current = true;
    setSaving(true);
    let updated: Sku;
    try {
      updated = await updateSku(sku.id, payload);
    } catch (error: unknown) {
      const result = catalogueSaveFailure(error);
      setFailure(result.message);
      setServerErrors(result.fields);
      focusError(result.fields);
      return;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
    onSaved(updated);
    onClose();
  }

  function field(
    name: CatalogueEditorField,
    label: string,
    helperText?: string,
    numeric = false,
  ) {
    return (
      <TextInput
        id={`catalogue-edit-${name}`}
        key={name}
        labelText={label}
        value={form[name]}
        onChange={(event) => update(name, event.target.value)}
        helperText={helperText}
        inputMode={numeric ? "decimal" : undefined}
        invalid={Boolean(errors[name])}
        invalidText={errors[name]}
        disabled={saving}
      />
    );
  }

  return (
    <Modal
      open
      size="lg"
      className={styles.modal}
      hasScrollingContent
      modalLabel={
        discardOpen ? "UNSAVED CHANGES" : `CATALOGUE / ${sku.our_ref}`
      }
      modalHeading={discardOpen ? "Discard your changes?" : "Edit SKU"}
      selectorPrimaryFocus="#catalogue-edit-name"
      preventCloseOnClickOutside
      shouldSubmitOnEnter={false}
      onRequestClose={requestClose}
      onSecondarySubmit={() =>
        discardOpen ? setDiscardOpen(false) : requestClose()
      }
      onRequestSubmit={() => {
        void save();
      }}
      danger={discardOpen}
      primaryButtonText={
        discardOpen ? "Discard changes" : saving ? "Saving…" : "Save changes"
      }
      primaryButtonDisabled={saving || (!discardOpen && !dirty)}
      secondaryButtonText={discardOpen ? "Keep editing" : "Cancel"}
    >
      {discardOpen ? (
        <div className={styles.discard}>
          <p>
            You have unsaved changes to <strong>{sku.name}</strong>.
          </p>
          <p>Discard them to close the editor, or keep editing to continue.</p>
        </div>
      ) : (
        <>
          <div className={styles.identity}>
            <div className={styles.identityIcon}>
              <Catalog size={28} />
            </div>
            <div>
              <strong>{sku.name}</strong>
              <span>
                {sku.our_ref} · {sku.category ?? "Uncategorised"}
              </span>
            </div>
            <Tag
              type={dirty ? "blue" : "gray"}
              size="sm"
              className={styles.status}
            >
              {dirty ? "Unsaved changes" : "No changes"}
            </Tag>
          </div>
          <div className={styles.layout}>
            <div className={styles.form}>
              <Tabs
                selectedIndex={tab}
                onChange={({ selectedIndex }) => setTab(selectedIndex)}
              >
                <TabList aria-label="Edit SKU sections">
                  <Tab disabled={saving}>Product details</Tab>
                  <Tab disabled={saving}>Pricing</Tab>
                  <Tab disabled={saving}>Supply &amp; ordering</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel>
                    <div className={styles.heading}>
                      <h3>Product details</h3>
                      <p>Keep this product easy to find and identify.</p>
                    </div>
                    <div className={styles.fields}>
                      <div className={styles.wide}>
                        {field("name", "Product name *")}
                      </div>
                      {field(
                        "design",
                        "Design *",
                        "Collection or design name.",
                      )}
                      {field(
                        "fabric",
                        "Fabric / material *",
                        "Use N/A when it does not apply.",
                      )}
                      {field(
                        "our_ref",
                        "SKU / Our reference *",
                        "Your reference for this product.",
                      )}
                      {field(
                        "our_barcode",
                        "Our barcode *",
                        "Used on Firstout’s barcode labels.",
                      )}
                      <div className={styles.wide}>
                        {field(
                          "category",
                          "Category",
                          "Optional. Choose an existing category below or enter a new one.",
                        )}
                        <Select
                          id="catalogue-edit-category-choice"
                          labelText="Existing category"
                          hideLabel
                          value={
                            categoryOptions.includes(form.category)
                              ? form.category
                              : ""
                          }
                          onChange={(event) =>
                            update("category", event.target.value)
                          }
                          disabled={saving}
                        >
                          <SelectItem
                            value=""
                            text="Choose a category or leave blank"
                          />
                          {categoryOptions.map((category) => (
                            <SelectItem
                              key={category}
                              value={category}
                              text={category}
                            />
                          ))}
                        </Select>
                      </div>
                    </div>
                  </TabPanel>
                  <TabPanel>
                    <div className={styles.heading}>
                      <h3>Pricing</h3>
                      <p>
                        Sale prices are in South African rand and include VAT.
                      </p>
                    </div>
                    {unitCost !== undefined && (
                      <div className={styles.cost}>
                        <TextInput
                          id="catalogue-edit-cost"
                          labelText="Unit cost (ZAR)"
                          value={
                            costLoading
                              ? "Loading…"
                              : unitCost === null
                                ? "Unavailable"
                                : formatZarAmount(unitCost)
                          }
                          readOnly
                          helperText="Read only. Calculated from inventory receipts."
                        />
                        <Information size={18} />
                      </div>
                    )}
                    <div className={styles.fields}>
                      {CATALOGUE_PRICE_FIELDS.map((price) =>
                        field(
                          price,
                          `${priceLabels[price]} (ZAR)`,
                          "Includes VAT. Leave blank if not set.",
                          true,
                        ),
                      )}
                    </div>
                    <p className={styles.helper}>
                      Changing a sale price also updates its ex-VAT value. Other
                      price tiers remain unchanged.
                    </p>
                  </TabPanel>
                  <TabPanel>
                    <div className={styles.heading}>
                      <h3>Supply &amp; ordering</h3>
                      <p>
                        Keep supplier references and ordering defaults together.
                      </p>
                    </div>
                    <div className={styles.fields}>
                      <Select
                        id="catalogue-edit-preferred_supplier_id"
                        labelText="Preferred supplier"
                        value={form.preferred_supplier_id}
                        onChange={(event) =>
                          update("preferred_supplier_id", event.target.value)
                        }
                        invalid={Boolean(errors.preferred_supplier_id)}
                        invalidText={errors.preferred_supplier_id}
                        disabled={saving}
                      >
                        <SelectItem value="" text="No preferred supplier" />
                        {sku.preferred_supplier_id &&
                          !suppliers.some(
                            (supplier) =>
                              supplier.id === sku.preferred_supplier_id,
                          ) && (
                            <SelectItem
                              value={sku.preferred_supplier_id}
                              text={
                                sku.preferred_supplier_name ??
                                "Current supplier"
                              }
                            />
                          )}
                        {suppliers.map((supplier) => (
                          <SelectItem
                            key={supplier.id}
                            value={supplier.id}
                            text={supplier.name}
                          />
                        ))}
                      </Select>
                      {field(
                        "supplier_ref",
                        "Supplier reference",
                        "The supplier’s code, separate from our barcode.",
                      )}
                      {field(
                        "lead_time_days",
                        "Planned lead time (days)",
                        "Whole days, 0 or more. Leave blank if unknown.",
                        true,
                      )}
                      {field(
                        "carton_count",
                        "Cartons per product *",
                        "Whole cartons, at least 1.",
                        true,
                      )}
                      {field(
                        "reorder_min",
                        "Reorder minimum (units)",
                        "Whole units, at least 1. Leave blank if not set.",
                        true,
                      )}
                    </div>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </div>
            <aside className={styles.summary}>
              <span className={styles.summaryLabel}>PRODUCT SUMMARY</span>
              <h3>{form.name.trim() || "Untitled product"}</h3>
              <p>{form.category.trim() || "Uncategorised"}</p>
              <div className={styles.retail}>
                <span>Retail price · incl. VAT</span>
                <strong>
                  {form.retail_inc_vat.trim() &&
                  Number.isFinite(Number(form.retail_inc_vat))
                    ? formatZarAmount(form.retail_inc_vat)
                    : "—"}
                </strong>
              </div>
              <dl>
                <div>
                  <dt>SKU</dt>
                  <dd>{form.our_ref}</dd>
                </div>
                <div>
                  <dt>Preferred supplier</dt>
                  <dd>{supplierName ?? "Not set"}</dd>
                </div>
                <div>
                  <dt>Planned lead time</dt>
                  <dd>
                    {form.lead_time_days.trim()
                      ? `${form.lead_time_days} days`
                      : "Not set"}
                  </dd>
                </div>
              </dl>
            </aside>
          </div>
          {failure && (
            <div className={styles.failure}>
              <InlineNotification
                kind="error"
                lowContrast
                hideCloseButton
                title="SKU not saved"
                subtitle={failure}
              />
            </div>
          )}
          <div className={styles.note}>
            <span>* Required fields</span>
            <span>
              {saving
                ? "Saving your changes…"
                : dirty
                  ? "Your changes have not been saved yet."
                  : "Update a field to save changes."}
            </span>
          </div>
        </>
      )}
    </Modal>
  );
}
