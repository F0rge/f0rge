"use client";

import { StaffImage } from "@/components/staff-image";

import {
  Button,
  FileUploaderDropContainer,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  SkeletonText,
  Stack,
  Tab,
  TabListVertical,
  TabPanel,
  TabPanels,
  TabsVertical,
  TextArea,
  TextInput,
  Tile,
  Toggle,
  Tag,
} from "@carbon/react";
import { ChevronDown, ChevronUp, Close, Settings } from "@carbon/icons-react";
import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  canManageUsers,
  canMutateSettings,
  getSettings,
  isActiveLocation,
  listLocations,
  settingsLogoUrl,
  updateSettings,
  uploadCompanyLogo,
  type AppSettings,
  type DocumentSequence,
  type Location,
} from "@/lib/api";
import { LabelSettings } from "@/app/settings/label-settings";
import { CommunicationsSettings } from "@/app/settings/communications-settings";
import { PaymentRemindersSettings } from "@/app/settings/payment-reminders-settings";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import {
  CommunicationsLoading,
  PaymentRemindersLoading,
  SettingsPanelLoading,
} from "./loading-layout";
import styles from "./settings.module.css";

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: "Invoice",
  credit_note: "Credit note",
  bill: "Bill",
  payment: "Payment",
  purchase_order: "Purchase order",
  delivery: "Delivery",
  stock_return: "Return",
  journal: "Journal",
  layby: "Layby",
  transfer: "Transfer",
  pick: "Pick",
};

function docTypeLabel(docType: string): string {
  return DOC_TYPE_LABELS[docType] ?? docType;
}

function SettingsSaveButton({
  canMutate,
  saving,
  onSave,
  onDiscard,
  dirty,
}: {
  canMutate: boolean;
  saving: boolean;
  onSave: () => void;
  onDiscard: () => void;
  dirty: boolean;
}) {
  if (!canMutate) {
    return (
      <InlineNotification
        kind="info"
        title="Read only"
        subtitle="You do not have permission to change settings."
        hideCloseButton
      />
    );
  }
  return (
    <div className={styles.saveActions}>
      <Button kind="primary" disabled={saving || !dirty} onClick={onSave}>
        {saving ? "Saving…" : "Save settings"}
      </Button>
      <Button kind="ghost" disabled={saving || !dirty} onClick={onDiscard}>
        Discard changes
      </Button>
      {dirty ? <Tag type="warm-gray">Unsaved changes</Tag> : null}
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const canMutate = canMutateSettings(user);
  const canConfigureReminders = canManageUsers(user);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [savedRootDraft, setSavedRootDraft] = useState("");
  const [vatPercent, setVatPercent] = useState("15");
  const [currency, setCurrency] = useState("ZAR");
  const [legalName, setLegalName] = useState("");
  const [tradingName, setTradingName] = useState("");
  const [address, setAddress] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [cipcNumber, setCipcNumber] = useState("");
  const [bankName, setBankName] = useState("");
  const [bankAccount, setBankAccount] = useState("");
  const [bankBranchCode, setBankBranchCode] = useState("");
  const [paymentTermsDays, setPaymentTermsDays] = useState(30);
  const [maxTillDiscountPercent, setMaxTillDiscountPercent] = useState("");
  const [poApprovalThresholdZar, setPoApprovalThresholdZar] = useState("");
  const [hasLogo, setHasLogo] = useState(false);
  const [logoUploading, setLogoUploading] = useState(false);
  const [logoVersion, setLogoVersion] = useState(0);
  const [defaultReceiveLocationId, setDefaultReceiveLocationId] = useState("");
  const [defaultTillLocationId, setDefaultTillLocationId] = useState("");
  const [documentSequences, setDocumentSequences] = useState<
    DocumentSequence[]
  >([]);
  const [preferWarehouse, setPreferWarehouse] = useState(true);
  const [autoProcessExactInvoices, setAutoProcessExactInvoices] =
    useState(false);
  const [pickPriority, setPickPriority] = useState<string[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [addLocationId, setAddLocationId] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const warehouses = useMemo(
    () => locations.filter((location) => location.type === "warehouse"),
    [locations],
  );
  const showrooms = useMemo(
    () => locations.filter((location) => location.type === "showroom"),
    [locations],
  );

  function applySettings(data: AppSettings) {
    setSettings(data);
    setSavedRootDraft(
      JSON.stringify([
        data.vat_percent,
        data.home_currency,
        data.legal_name,
        data.trading_name ?? "",
        data.address,
        data.vat_number,
        data.cipc_number ?? "",
        data.bank_name ?? "",
        data.bank_account ?? "",
        data.bank_branch_code ?? "",
        data.payment_terms_days,
        data.max_till_discount_percent ?? "",
        data.po_approval_threshold_zar ?? "",
        data.default_receive_location_id ?? "",
        data.default_till_location_id ?? "",
        data.document_sequences.map(({ doc_type, prefix, padding }) => ({
          doc_type,
          prefix,
          padding,
        })),
        data.always_prefer_warehouse,
        data.auto_process_exact_supplier_invoices,
        data.pick_priority,
      ]),
    );
    setVatPercent(data.vat_percent);
    setCurrency(data.home_currency);
    setLegalName(data.legal_name);
    setTradingName(data.trading_name ?? "");
    setAddress(data.address);
    setVatNumber(data.vat_number);
    setCipcNumber(data.cipc_number ?? "");
    setBankName(data.bank_name ?? "");
    setBankAccount(data.bank_account ?? "");
    setBankBranchCode(data.bank_branch_code ?? "");
    setPaymentTermsDays(data.payment_terms_days);
    setMaxTillDiscountPercent(data.max_till_discount_percent ?? "");
    setPoApprovalThresholdZar(data.po_approval_threshold_zar ?? "");
    setHasLogo(data.has_logo);
    setDefaultReceiveLocationId(data.default_receive_location_id ?? "");
    setDefaultTillLocationId(data.default_till_location_id ?? "");
    setDocumentSequences(data.document_sequences);
    setPreferWarehouse(data.always_prefer_warehouse);
    setAutoProcessExactInvoices(data.auto_process_exact_supplier_invoices);
    setPickPriority(data.pick_priority);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSettings(), listLocations()])
      .then(([data, locationData]) => {
        if (!cancelled) {
          applySettings(data);
          setLocations(locationData.filter(isActiveLocation));
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Failed to load settings",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  async function handleSave() {
    if (saving || logoUploading) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const vatRate = (Number(vatPercent) / 100).toFixed(4);
      const updated = await updateSettings({
        vat_rate: vatRate,
        home_currency: currency.toUpperCase(),
        legal_name: legalName.trim(),
        trading_name: tradingName.trim() || null,
        address: address.trim(),
        vat_number: vatNumber.trim(),
        cipc_number: cipcNumber.trim() || null,
        bank_name: bankName.trim() || null,
        bank_account: bankAccount.trim() || null,
        bank_branch_code: bankBranchCode.trim() || null,
        payment_terms_days: paymentTermsDays,
        max_till_discount_percent: maxTillDiscountPercent.trim()
          ? maxTillDiscountPercent.trim()
          : null,
        po_approval_threshold_zar: poApprovalThresholdZar.trim()
          ? poApprovalThresholdZar.trim()
          : null,
        default_receive_location_id: defaultReceiveLocationId || null,
        default_till_location_id: defaultTillLocationId || null,
        document_sequences: documentSequences.map((row) => ({
          doc_type: row.doc_type,
          prefix: row.prefix,
          padding: row.padding,
        })),
        always_prefer_warehouse: preferWarehouse,
        auto_process_exact_supplier_invoices: autoProcessExactInvoices,
        pick_priority: pickPriority,
      });
      applySettings(updated);
      setNotice(updated.warning ?? "Settings saved.");
    } catch (err: unknown) {
      setError(
        err instanceof ApiError ? err.message : "Failed to save settings",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleLogoUpload(file: File) {
    setLogoUploading(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await uploadCompanyLogo(file);
      setSettings(updated);
      setHasLogo(updated.has_logo);
      setLogoVersion((version) => version + 1);
      setNotice("Company logo uploaded.");
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Failed to upload logo");
    } finally {
      setLogoUploading(false);
    }
  }

  function updateSequence(
    docType: string,
    patch: Partial<Pick<DocumentSequence, "prefix" | "padding">>,
  ) {
    setDocumentSequences((current) =>
      current.map((row) =>
        row.doc_type === docType ? { ...row, ...patch } : row,
      ),
    );
  }

  const pickPrioritySection = (
    <Stack gap={3}>
      <p className="cds--label">Pick priority</p>
      <p className="firstout-muted-text">
        Ordered location list for kit picks. Empty derives order by location
        type.
      </p>
      {pickPriority.length === 0 ? (
        <p className="cds--type-body-01">No priority set — derive by type.</p>
      ) : (
        pickPriority.map((locationId, index) => {
          const location = locations.find((entry) => entry.id === locationId);
          return (
            <div key={locationId} className="firstout-pick-priority-row">
              <span>
                {index + 1}. {location?.name ?? locationId}
              </span>
              <div className="firstout-catalogue-actions">
                <Button
                  kind="ghost"
                  size="sm"
                  hasIconOnly
                  renderIcon={ChevronUp}
                  iconDescription="Move up"
                  disabled={!canMutate || saving || index === 0}
                  onClick={() =>
                    setPickPriority((current) => {
                      const next = [...current];
                      const swap = next[index - 1];
                      next[index - 1] = next[index];
                      next[index] = swap;
                      return next;
                    })
                  }
                />
                <Button
                  kind="ghost"
                  size="sm"
                  hasIconOnly
                  renderIcon={ChevronDown}
                  iconDescription="Move down"
                  disabled={
                    !canMutate || saving || index === pickPriority.length - 1
                  }
                  onClick={() =>
                    setPickPriority((current) => {
                      const next = [...current];
                      const swap = next[index + 1];
                      next[index + 1] = next[index];
                      next[index] = swap;
                      return next;
                    })
                  }
                />
                <Button
                  kind="ghost"
                  size="sm"
                  hasIconOnly
                  renderIcon={Close}
                  iconDescription="Remove"
                  disabled={!canMutate || saving}
                  onClick={() =>
                    setPickPriority((current) =>
                      current.filter((id) => id !== locationId),
                    )
                  }
                />
              </div>
            </div>
          );
        })
      )}
      <Select
        id="add-pick-priority"
        labelText="Add location"
        value={addLocationId}
        disabled={!canMutate || saving}
        onChange={(event) => {
          const nextId = event.target.value;
          if (!nextId) {
            return;
          }
          setPickPriority((current) =>
            current.includes(nextId) ? current : [...current, nextId],
          );
          setAddLocationId("");
        }}
      >
        <SelectItem value="" text="Select location" />
        {locations
          .filter((location) => !pickPriority.includes(location.id))
          .map((location) => (
            <SelectItem
              key={location.id}
              value={location.id}
              text={location.name}
            />
          ))}
      </Select>
    </Stack>
  );

  const dirty =
    !!settings &&
    JSON.stringify([
      vatPercent,
      currency,
      legalName,
      tradingName,
      address,
      vatNumber,
      cipcNumber,
      bankName,
      bankAccount,
      bankBranchCode,
      paymentTermsDays,
      maxTillDiscountPercent,
      poApprovalThresholdZar,
      defaultReceiveLocationId,
      defaultTillLocationId,
      documentSequences.map(({ doc_type, prefix, padding }) => ({
        doc_type,
        prefix,
        padding,
      })),
      preferWarehouse,
      autoProcessExactInvoices,
      pickPriority,
    ]) !== savedRootDraft;
  function discardChanges() {
    if (!settings || saving || logoUploading) return;
    applySettings(settings);
    setAddLocationId("");
    setError(null);
    setNotice(null);
  }

  return (
    <Stack gap={6} className={styles.workspace}>
      <div>
        <h1 className="cds--type-heading-05">Settings</h1>
        <p className="cds--type-body-01">
          Company profile, document numbering, and operations defaults. Changes
          are not filed with SARS.
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Settings"
          subtitle={error}
          hideCloseButton
        />
      ) : null}
      {notice ? (
        <InlineNotification
          kind={settings?.warning ? "warning" : "success"}
          title="Settings"
          subtitle={notice}
          hideCloseButton
        />
      ) : null}
      {settings?.warning && !notice ? (
        <InlineNotification
          kind="warning"
          title="Non-default settings"
          subtitle={settings.warning}
          hideCloseButton
        />
      ) : null}

      {!loading && !settings && error ? (
        <Button
          kind="secondary"
          onClick={() => {
            setError(null);
            setLoading(true);
            setAttempt((value) => value + 1);
          }}
        >
          Try again
        </Button>
      ) : null}
      {loading || settings ? (
        <div
          className={`${styles.intro} firstout-tone-info firstout-section-accent`}
        >
          <Settings size={32} aria-hidden="true" />
          <div>
            <h2 className="cds--type-heading-03">
              A workspace that works your way.
            </h2>
            <p className="cds--type-body-01">
              Set the defaults once. Give your team a consistent starting point.
            </p>
          </div>
          <Tag type="gray">
            {canMutate ? "Workspace settings" : "Read only"}
          </Tag>
        </div>
      ) : null}
      {loading || settings ? (
        <div className={styles.layout}>
          <div className={styles.tabs}>
            <TabsVertical>
              <TabListVertical aria-label="Settings sections">
                <Tab>Company</Tab>
                <Tab>Documents</Tab>
                <Tab>Locations</Tab>
                <Tab>Operations</Tab>
                <Tab>Labels</Tab>
                <Tab>Communications</Tab>
                {canConfigureReminders ? <Tab>Payment reminders</Tab> : null}
              </TabListVertical>
              <TabPanels>
                <TabPanel>
                  <Tile>
                    {loading ? <SettingsPanelLoading panel="Company" /> : <Stack gap={5}>
                      <h2 className="cds--type-heading-03">Company</h2>
                      <div className={styles.formGrid}>
                        <TextInput
                          id="legal-name"
                          labelText="Legal name"
                          value={legalName}
                          disabled={!canMutate || saving}
                          onChange={(event) => setLegalName(event.target.value)}
                        />
                        <TextInput
                          id="trading-name"
                          labelText="Trading name"
                          helperText="Optional — shown on documents when set."
                          value={tradingName}
                          disabled={!canMutate || saving}
                          onChange={(event) =>
                            setTradingName(event.target.value)
                          }
                        />
                      </div>
                      <TextArea
                        id="company-address"
                        labelText="Address"
                        value={address}
                        disabled={!canMutate || saving}
                        onChange={(event) => setAddress(event.target.value)}
                      />
                      <div className={styles.formGrid}>
                        <TextInput
                          id="company-vat-number"
                          labelText="VAT number"
                          value={vatNumber}
                          disabled={!canMutate || saving}
                          onChange={(event) => setVatNumber(event.target.value)}
                        />
                        <TextInput
                          id="cipc-number"
                          labelText="CIPC number"
                          helperText="Optional company registration number."
                          value={cipcNumber}
                          disabled={!canMutate || saving}
                          onChange={(event) =>
                            setCipcNumber(event.target.value)
                          }
                        />
                        <TextInput
                          id="bank-name"
                          labelText="Bank name"
                          value={bankName}
                          disabled={!canMutate || saving}
                          onChange={(event) => setBankName(event.target.value)}
                        />
                        <TextInput
                          id="bank-account"
                          labelText="Bank account"
                          value={bankAccount}
                          disabled={!canMutate || saving}
                          onChange={(event) =>
                            setBankAccount(event.target.value)
                          }
                        />
                        <TextInput
                          id="bank-branch-code"
                          labelText="Branch code"
                          value={bankBranchCode}
                          disabled={!canMutate || saving}
                          onChange={(event) =>
                            setBankBranchCode(event.target.value)
                          }
                        />
                      </div>
                      <div>
                        <p className="cds--type-label-01">Company logo</p>
                        <p className="firstout-muted-text cds--type-helper-text-01">
                          JPEG or PNG. Shown on tax invoices and till receipts.
                          Upload replaces any existing logo.
                        </p>
                        {hasLogo ? (
                          <StaffImage
                            className="firstout-company-logo"
                            src={`${settingsLogoUrl()}?v=${logoVersion}`}
                            alt="Company logo"
                          />
                        ) : null}
                        {canMutate ? (
                          <FileUploaderDropContainer
                            accept={["image/jpeg", "image/png"]}
                            labelText={
                              logoUploading
                                ? "Uploading logo…"
                                : "Drag and drop a logo here or click to upload"
                            }
                            multiple={false}
                            disabled={logoUploading}
                            onAddFiles={(_event, { addedFiles }) => {
                              const file = addedFiles[0];
                              if (file) {
                                void handleLogoUpload(file);
                              }
                            }}
                          />
                        ) : null}
                      </div>
                      <NumberInput
                        id="vat-percent"
                        label="VAT rate (%)"
                        helperText="Locked default is 15%. Owner may adjust for what-if only."
                        value={vatPercent}
                        min={0}
                        max={100}
                        step={0.01}
                        disabled={!canMutate || saving}
                        onChange={(_, { value }) => {
                          if (
                            typeof value === "number" ||
                            typeof value === "string"
                          ) {
                            setVatPercent(String(value));
                          }
                        }}
                      />
                      <TextInput
                        id="home-currency"
                        labelText="Home currency"
                        helperText="Locked default is ZAR."
                        value={currency}
                        maxLength={3}
                        disabled={!canMutate || saving}
                        onChange={(event) =>
                          setCurrency(event.target.value.toUpperCase())
                        }
                      />
                      <SettingsSaveButton
                        canMutate={canMutate}
                        saving={saving || logoUploading}
                        dirty={dirty}
                        onDiscard={discardChanges}
                        onSave={() => void handleSave()}
                      />
                    </Stack>}
                  </Tile>
                </TabPanel>

                <TabPanel>
                  <Tile>
                    {loading ? <SettingsPanelLoading panel="Documents" /> : <Stack gap={5}>
                      <h2 className="cds--type-heading-03">Documents</h2>
                      <p className="cds--type-body-01 firstout-muted-text">
                        Prefix and padding apply to new documents. Cancelled
                        documents keep their numbers — next value only advances
                        on allocation.
                      </p>
                      <div className="firstout-settings-sequences">
                        <div className="firstout-settings-sequences__header cds--type-label-01">
                          <span>Document type</span>
                          <span>Prefix</span>
                          <span>Padding</span>
                          <span>Next value</span>
                        </div>
                        {documentSequences.map((row) => (
                          <div
                            key={row.doc_type}
                            className="firstout-settings-sequences__row"
                          >
                            <span className="cds--type-body-01">
                              {docTypeLabel(row.doc_type)}
                            </span>
                            <TextInput
                              id={`seq-prefix-${row.doc_type}`}
                              labelText=""
                              hideLabel
                              value={row.prefix}
                              maxLength={8}
                              disabled={!canMutate || saving}
                              onChange={(event) =>
                                updateSequence(row.doc_type, {
                                  prefix: event.target.value,
                                })
                              }
                            />
                            <NumberInput
                              id={`seq-padding-${row.doc_type}`}
                              label=""
                              hideLabel
                              min={1}
                              max={12}
                              step={1}
                              value={row.padding}
                              disabled={!canMutate || saving}
                              onChange={(_, { value }) => {
                                if (typeof value === "number") {
                                  updateSequence(row.doc_type, {
                                    padding: value,
                                  });
                                }
                              }}
                            />
                            <TextInput
                              id={`seq-next-${row.doc_type}`}
                              labelText=""
                              hideLabel
                              value={String(row.next_value)}
                              readOnly
                              disabled
                            />
                          </div>
                        ))}
                      </div>
                      <SettingsSaveButton
                        canMutate={canMutate}
                        saving={saving || logoUploading}
                        dirty={dirty}
                        onDiscard={discardChanges}
                        onSave={() => void handleSave()}
                      />
                    </Stack>}
                  </Tile>
                </TabPanel>

                <TabPanel>
                  <Tile>
                    {loading ? <SettingsPanelLoading panel="Locations" /> : <Stack gap={5}>
                      <h2 className="cds--type-heading-03">Locations</h2>
                      <Select
                        id="default-receive-location"
                        labelText="Default receive location"
                        helperText="Warehouse locations only."
                        value={defaultReceiveLocationId}
                        disabled={!canMutate || saving}
                        onChange={(event) =>
                          setDefaultReceiveLocationId(event.target.value)
                        }
                      >
                        <SelectItem value="" text="None" />
                        {warehouses.map((location) => (
                          <SelectItem
                            key={location.id}
                            value={location.id}
                            text={location.name}
                          />
                        ))}
                      </Select>
                      <Select
                        id="default-till-location"
                        labelText="Default till location"
                        helperText="Showroom locations only."
                        value={defaultTillLocationId}
                        disabled={!canMutate || saving}
                        onChange={(event) =>
                          setDefaultTillLocationId(event.target.value)
                        }
                      >
                        <SelectItem value="" text="None" />
                        {showrooms.map((location) => (
                          <SelectItem
                            key={location.id}
                            value={location.id}
                            text={location.name}
                          />
                        ))}
                      </Select>
                      <Toggle
                        id="always-prefer-warehouse"
                        labelText="Always prefer warehouse"
                        labelA="Off"
                        labelB="On"
                        toggled={preferWarehouse}
                        onToggle={(checked) => setPreferWarehouse(checked)}
                        disabled={!canMutate || saving}
                      />
                      <Toggle
                        id="auto-process-exact-invoices"
                        labelText="Auto-process exact supplier invoices"
                        labelA="Off"
                        labelB="On"
                        toggled={autoProcessExactInvoices}
                        onToggle={(checked) =>
                          setAutoProcessExactInvoices(checked)
                        }
                        disabled={!canMutate || saving}
                      />
                      <p className="cds--type-helper-text-01">
                        Off by default. When on, an invoice that matches its
                        purchase order exactly is posted like a typed-in bill,
                        without a second click. Anything that differs still
                        waits for you. A posted bill is reversed with a journal.
                      </p>
                      {pickPrioritySection}
                      <SettingsSaveButton
                        canMutate={canMutate}
                        saving={saving || logoUploading}
                        dirty={dirty}
                        onDiscard={discardChanges}
                        onSave={() => void handleSave()}
                      />
                    </Stack>}
                  </Tile>
                </TabPanel>

                <TabPanel>
                  <Tile>
                    {loading ? <SettingsPanelLoading panel="Operations" /> : <Stack gap={5}>
                      <h2 className="cds--type-heading-03">Operations</h2>
                      <NumberInput
                        id="payment-terms-days"
                        label="Default payment terms (days)"
                        helperText="Used for new invoices when a customer has no override."
                        value={paymentTermsDays}
                        min={0}
                        max={365}
                        step={1}
                        disabled={!canMutate || saving}
                        onChange={(_, { value }) => {
                          if (typeof value === "number") {
                            setPaymentTermsDays(value);
                          }
                        }}
                      />
                      <NumberInput
                        id="max-till-discount-percent"
                        label="Max till discount (%)"
                        helperText="Empty = no cap. 0 is a valid cap."
                        value={maxTillDiscountPercent}
                        min={0}
                        max={100}
                        step={0.01}
                        disabled={!canMutate || saving}
                        onChange={(_, { value }) => {
                          if (
                            typeof value === "number" ||
                            typeof value === "string"
                          ) {
                            setMaxTillDiscountPercent(String(value));
                          }
                        }}
                      />
                      <NumberInput
                        id="po-approval-threshold-zar"
                        label="PO approval threshold (ZAR)"
                        helperText="Empty = no cap. POs above this need users.manage to create."
                        value={poApprovalThresholdZar}
                        min={0}
                        step={0.01}
                        disabled={!canMutate || saving}
                        onChange={(_, { value }) => {
                          if (
                            typeof value === "number" ||
                            typeof value === "string"
                          ) {
                            setPoApprovalThresholdZar(String(value));
                          }
                        }}
                      />
                      <p className="cds--type-body-01">
                        Clerk manages sign-in session duration and security.
                      </p>
                      <SettingsSaveButton
                        canMutate={canMutate}
                        saving={saving || logoUploading}
                        dirty={dirty}
                        onDiscard={discardChanges}
                        onSave={() => void handleSave()}
                      />
                    </Stack>}
                  </Tile>
                </TabPanel>

                <TabPanel>
                  <Tile>
                    {loading ? <SettingsPanelLoading panel="Labels" /> : settings && (
                      <>
                        <h2 className="cds--type-heading-03">Labels</h2>
                        <LabelSettings settings={settings} canMutate={canMutate} />
                      </>
                    )}
                  </Tile>
                </TabPanel>
                <TabPanel>
                  <Tile>
                    {loading ? <CommunicationsLoading /> : <CommunicationsSettings />}
                  </Tile>
                </TabPanel>

                {canConfigureReminders ? (
                  <TabPanel>
                    <Tile>
                      {loading ? <PaymentRemindersLoading /> : <PaymentRemindersSettings />}
                    </Tile>
                  </TabPanel>
                ) : null}
              </TabPanels>
            </TabsVertical>
          </div>
          <aside className={styles.aside}>
            <Tile>
              <Stack gap={5}>
                <h2 className="cds--type-heading-compact-01">
                  Before you save
                </h2>
                <p className="cds--type-body-01">
                  Changes apply to this organisation. Review operational
                  defaults with your team before saving.
                </p>
                {loading ? (
                  <div className="firstout-loading-motion" aria-hidden="true"><SkeletonText width="3rem" /></div>
                ) : <Tag type="gray">{settings?.home_currency}</Tag>}
                <Link href="/organisation" className="cds--link">
                  Organisation and staff access
                </Link>
              </Stack>
            </Tile>
          </aside>
        </div>
      ) : null}
    </Stack>
  );
}
