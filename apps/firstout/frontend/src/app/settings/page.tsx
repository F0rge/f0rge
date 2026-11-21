"use client";

import { StaffImage } from "@/components/staff-image";

import {
  Button,
  FileUploaderDropContainer,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextArea,
  TextInput,
  Tile,
  Toggle,
} from "@carbon/react";
import { ChevronDown, ChevronUp, Close } from "@carbon/icons-react";
import { Suspense, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  ApiError,
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
import { useAuth } from "@/lib/auth";
import { AdminDirectoryLinks, AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import { ADMIN_DESTINATIONS, SETTINGS_SECTIONS, findSettingsSection, type SettingsSection } from "@/lib/admin-navigation";
import { AdminSaveActions, confirmDiscardChanges } from "@/components/admin-save-actions";
import { changedSettingsFields, useSettingsDrafts, type SettingsDraft } from "@/components/settings-drafts";
import { SettingsPanelLoading } from "./loading-layout";
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
  quote: "Quote",
  sales_order: "Sales order",
};

function docTypeLabel(docType: string): string {
  return DOC_TYPE_LABELS[docType] ?? docType;
}

function SettingsForm({ section }: { section: SettingsSection }) {
  const { user } = useAuth();
  const canMutate = canMutateSettings(user);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const drafts = useSettingsDrafts();
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
  const [tillHoldHours, setTillHoldHours] = useState("3");
  const holdHours = Number(tillHoldHours);
  // Empty reads as 0, so the range check also rejects it.
  const holdHoursValid = Number.isInteger(holdHours) && holdHours >= 1 && holdHours <= 24;
  const [documentSequences, setDocumentSequences] = useState<
    DocumentSequence[]
  >([]);
  const [selectedDocumentType, setSelectedDocumentType] = useState("invoice");
  const activeSequence = documentSequences.find((row) => row.doc_type === selectedDocumentType) ?? documentSequences[0];
  const [preferWarehouse, setPreferWarehouse] = useState(true);
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

  function applySettings(saved: AppSettings, draft?: SettingsDraft) {
    const data = { ...saved, ...draft?.fields };
    setSettings(saved);
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
    setTillHoldHours(String(data.till_hold_hours));
    setDocumentSequences(data.document_sequences.map((entry) =>
      draft?.sequence?.doc_type === entry.doc_type ? { ...entry, ...draft.sequence } : entry,
    ));
    if (draft?.sequence) setSelectedDocumentType(draft.sequence.doc_type);
    setPreferWarehouse(data.always_prefer_warehouse);
    setPickPriority(data.pick_priority);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([getSettings(), section === "locations" ? listLocations() : Promise.resolve([])])
      .then(([data, locationData]) => {
        if (!cancelled) {
          applySettings(data, canMutate ? drafts.get(section) : undefined);
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
  }, [attempt, canMutate, drafts, section]);

  async function handleSave() {
    if (saving || logoUploading) return;
    const submittedDraft = drafts.get(section);
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      let patch: Parameters<typeof updateSettings>[0];
      switch (section) {
        case "company":
          patch = {
            vat_rate: (Number(vatPercent) / 100).toFixed(4),
            home_currency: currency.toUpperCase(),
            legal_name: legalName.trim(),
            trading_name: tradingName.trim() || null,
            address: address.trim(),
            vat_number: vatNumber.trim(),
            cipc_number: cipcNumber.trim() || null,
            bank_name: bankName.trim() || null,
            bank_account: bankAccount.trim() || null,
            bank_branch_code: bankBranchCode.trim() || null,
          };
          break;
        case "documents":
          if (!activeSequence) return;
          patch = { document_sequences: [{
            doc_type: activeSequence.doc_type,
            prefix: activeSequence.prefix,
            padding: activeSequence.padding,
          }] };
          break;
        case "locations":
          if (!holdHoursValid) return;
          patch = {
            default_receive_location_id: defaultReceiveLocationId || null,
            default_till_location_id: defaultTillLocationId || null,
            till_hold_hours: holdHours,
            always_prefer_warehouse: preferWarehouse,
            pick_priority: pickPriority,
          };
          break;
        case "operations":
          patch = {
            payment_terms_days: paymentTermsDays,
            max_till_discount_percent: maxTillDiscountPercent.trim() || null,
            po_approval_threshold_zar: poApprovalThresholdZar.trim() || null,
          };
          break;
        default:
          return;
      }
      const updated = await updateSettings(patch);
      if (drafts.get(section) === submittedDraft) drafts.set(section);
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

  let fields: Partial<AppSettings> = {};
  switch (section) {
    case "company":
      fields = {
        vat_percent: vatPercent,
        home_currency: currency,
        legal_name: legalName,
        trading_name: tradingName || null,
        address,
        vat_number: vatNumber,
        cipc_number: cipcNumber || null,
        bank_name: bankName || null,
        bank_account: bankAccount || null,
        bank_branch_code: bankBranchCode || null,
      };
      break;
    case "locations":
      fields = {
        default_receive_location_id: defaultReceiveLocationId || null,
        default_till_location_id: defaultTillLocationId || null,
        till_hold_hours: holdHours,
        always_prefer_warehouse: preferWarehouse,
        pick_priority: pickPriority,
      };
      break;
    case "operations":
      fields = {
        payment_terms_days: paymentTermsDays,
        max_till_discount_percent: maxTillDiscountPercent || null,
        po_approval_threshold_zar: poApprovalThresholdZar || null,
      };
      break;
  }
  const changed = settings ? changedSettingsFields(settings, fields) : {};
  const savedSequence = settings?.document_sequences.find((entry) => entry.doc_type === activeSequence?.doc_type);
  const sequence = savedSequence && activeSequence &&
    (savedSequence.prefix !== activeSequence.prefix || savedSequence.padding !== activeSequence.padding)
    ? { doc_type: activeSequence.doc_type, prefix: activeSequence.prefix, padding: activeSequence.padding }
    : undefined;
  const dirty = Object.keys(changed).length > 0 || !!sequence;

  useLayoutEffect(() => {
    if (settings && section !== "labels") {
      drafts.set(section, dirty && canMutate ? { fields: changed, sequence } : undefined);
    }
  });

  function discardChanges() {
    if (!settings || saving || logoUploading) return;
    drafts.set(section);
    applySettings(settings);
    setAddLocationId("");
    setError(null);
    setNotice(null);
  }

  const panel = SETTINGS_SECTIONS.find((item) => item.id === section)!;
  return (
    <Stack gap={5}>
      {error ? <InlineNotification kind="error" title="Settings" subtitle={error} hideCloseButton lowContrast /> : null}
      {notice || settings?.warning ? (
        <InlineNotification
          kind={settings?.warning ? "warning" : "success"}
          title={settings?.warning ? "Non-default settings" : "Settings"}
          subtitle={notice ?? settings?.warning ?? undefined}
          hideCloseButton
          lowContrast
        />
      ) : null}
      {!loading && !settings && error ? (
        <Button kind="secondary" onClick={() => { setError(null); setLoading(true); setAttempt((value) => value + 1); }}>
          Try again
        </Button>
      ) : null}
      {loading ? <Tile className={styles.panel}><SettingsPanelLoading panel={panel.label} /></Tile> : settings ? (
        <Tile className={styles.panel}>
          {section === "labels" ? <LabelSettings settings={settings} canMutate={canMutate} /> : (
            <Stack gap={5}>
              {section === "company" ? (
                <>
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
                </>
              ) : null}
              {section === "documents" ? (
                <>
                  <Select
                    id="document-type"
                    labelText="Document type"
                    value={activeSequence?.doc_type ?? ""}
                    onChange={(event) => {
                      if (!confirmDiscardChanges(dirty)) return;
                      discardChanges();
                      setSelectedDocumentType(event.target.value);
                    }}
                    disabled={saving || documentSequences.length === 0}
                  >
                    {documentSequences.length === 0 ? <SelectItem value="" text="No document sequences" /> : null}
                    {documentSequences.map((row) => (
                      <SelectItem key={row.doc_type} value={row.doc_type} text={docTypeLabel(row.doc_type)} />
                    ))}
                  </Select>
                  {activeSequence ? (
                    <div className={styles.formGrid}>
                      <TextInput
                        id="sequence-prefix"
                        labelText="Prefix"
                        value={activeSequence.prefix}
                        maxLength={8}
                        disabled={!canMutate || saving}
                        onChange={(event) => updateSequence(activeSequence.doc_type, { prefix: event.target.value })}
                      />
                      <NumberInput
                        id="sequence-padding"
                        label="Padding"
                        min={1}
                        max={12}
                        step={1}
                        value={activeSequence.padding}
                        disabled={!canMutate || saving}
                        onChange={(_, { value }) => {
                          if (typeof value === "number") updateSequence(activeSequence.doc_type, { padding: value });
                        }}
                      />
                      <TextInput id="sequence-next" labelText="Next value" value={String(activeSequence.next_value)} readOnly />
                    </div>
                  ) : null}
                  <p className="cds--type-helper-text-01">Prefix and padding apply to new documents. Cancelled documents keep their numbers.</p>
                </>
              ) : null}
              {section === "locations" ? (
                <>
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
                  <div className={styles.formGrid}>
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
                    <NumberInput
                      id="till-hold-hours"
                      allowEmpty
                      label="Sale hold time (hours)"
                      helperText="Applies to every till. An open sale expires this long after its last change; a held sale this long after it was held or resumed. Expiry deletes the sale and releases its reserved stock."
                      invalid={!holdHoursValid}
                      invalidText="Enter a whole number of hours from 1 to 24."
                      value={tillHoldHours}
                      min={1}
                      max={24}
                      step={1}
                      disabled={!canMutate || saving}
                      onChange={(_, { value }) => {
                        if (typeof value === "number" || typeof value === "string") {
                          setTillHoldHours(String(value));
                        }
                      }}
                    />
                  </div>
                  <Toggle
                    id="always-prefer-warehouse"
                    labelText="Always prefer warehouse"
                    labelA="Off"
                    labelB="On"
                    toggled={preferWarehouse}
                    onToggle={(checked) => setPreferWarehouse(checked)}
                    disabled={!canMutate || saving}
                  />
                  {pickPrioritySection}
                </>
              ) : null}
              {section === "operations" ? (
                <>
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
                    allowEmpty
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
                    allowEmpty
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
                </>
              ) : null}
              <AdminSaveActions canMutate={canMutate} saving={saving || logoUploading} dirty={dirty} saveDisabled={section === "locations" && !holdHoursValid} onDiscard={discardChanges} onSave={() => void handleSave()} />
            </Stack>
          )}
        </Tile>
      ) : null}
    </Stack>
  );
}

function SettingsContent() {
  const section = findSettingsSection(useSearchParams().get("tab"));
  if (section) {
    return (
      <Stack gap={6}>
        <AdminPageHeader title={section.label} description={section.description} />
        <SettingsForm key={section.id} section={section.id} />
      </Stack>
    );
  }

  const { label, description } = ADMIN_DESTINATIONS.settings;
  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description} />
      {(["Business", "Operations"] as const).map((group) => (
        <Stack key={group} gap={4}>
          <h2 className="cds--type-heading-03">{group}</h2>
          <AdminDirectoryLinks items={SETTINGS_SECTIONS.filter((entry) => entry.group === group).map(({ id }) => id)} />
        </Stack>
      ))}
      <Stack gap={4}>
        <h2 className="cds--type-heading-03">Integrations</h2>
        <AdminDirectoryLinks items={["integrations"]} />
      </Stack>
    </Stack>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<PageLoading kind="status" label="Loading settings…" />}>
      <SettingsContent />
    </Suspense>
  );
}
