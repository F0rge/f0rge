"use client";

import { SkeletonPlaceholder, SkeletonText, Stack } from "@carbon/react";
import { LoadingField, LoadingRegion } from "@/components/page-loading";
import styles from "./settings.module.css";

function Fields({ labels }: { labels: readonly string[] }) {
  return labels.map((label) => <LoadingField key={label} label={label} />);
}

export function SettingsPanelLoading({ panel }: { panel: "Company" | "Documents" | "Locations" | "Operations" | "Labels" }) {
  return (
    <LoadingRegion label={`Loading ${panel.toLowerCase()} settings…`}>
      <Stack gap={5}>
        {panel === "Company" ? (
          <>
            <div className={styles.formGrid}>
              <LoadingField label="Legal name" />
              <LoadingField label="Trading name" helperText="Optional — shown on documents when set." />
            </div>
            <LoadingField label="Address" height="6rem" />
            <div className={styles.formGrid}>
              <LoadingField label="VAT number" />
              <LoadingField label="CIPC number" helperText="Optional company registration number." />
              <Fields labels={["Bank name", "Bank account", "Branch code"]} />
            </div>
            <div>
              <p className="cds--type-label-01">Company logo</p>
              <p className="firstout-muted-text cds--type-helper-text-01">
                JPEG or PNG. Shown on tax invoices and till receipts. Upload replaces any existing logo.
              </p>
              <SkeletonPlaceholder aria-hidden="true" style={{ width: "100%", height: "4rem" }} />
            </div>
            <LoadingField label="VAT rate (%)" helperText="Locked default is 15%. Owner may adjust for what-if only." />
            <LoadingField label="Home currency" helperText="Locked default is ZAR." />
          </>
        ) : panel === "Documents" ? (
          <>
            <LoadingField label="Document type" />
            <div className={styles.formGrid}>
              <Fields labels={["Prefix", "Padding", "Next value"]} />
            </div>
          </>
        ) : panel === "Locations" ? (
          <>
            <LoadingField label="Default receive location" helperText="Warehouse locations only." />
            <LoadingField label="Default till location" helperText="Showroom locations only." />
            <ToggleLoading label="Always prefer warehouse" />
            <ToggleLoading label="Auto-process exact supplier invoices" />
            <p className="cds--type-helper-text-01">
              Off by default. When on, an invoice that matches its purchase order exactly is posted like a typed-in bill, without a second click. Anything that differs still waits for you. A posted bill is reversed with a journal.
            </p>
            <p className="cds--type-body-01">Pick priority</p>
            <SkeletonText paragraph lineCount={2} width="60%" aria-hidden="true" />
          </>
        ) : panel === "Operations" ? (
          <>
            <LoadingField label="Default payment terms (days)" helperText="Used for new invoices when a customer has no override." />
            <LoadingField label="Max till discount (%)" helperText="Empty = no cap. 0 is a valid cap." />
            <LoadingField label="PO approval threshold (ZAR)" helperText="Empty = no cap. POs above this need users.manage to create." />
            <p className="cds--type-body-01">Clerk manages sign-in session duration and security.</p>
          </>
        ) : (
          <LabelSettingsLoading />
        )}
        <SkeletonPlaceholder aria-hidden="true" style={{ width: "8rem", height: "3rem" }} />
      </Stack>
    </LoadingRegion>
  );
}

function ToggleLoading({ label }: { label: string }) {
  return (
    <div>
      <p className="cds--label">{label}</p>
      <SkeletonPlaceholder aria-hidden="true" style={{ width: "5rem", height: "1.5rem" }} />
    </div>
  );
}

function LabelSettingsLoading() {
  return (
    <>
      <p>SKU and bin labels use these settings and your company logo.</p>
      <Fields labels={["Width (mm)", "Height (mm)"]} />
      {["Show name / bin position", "Show reference / bin code", "Show barcode", "Show company logo"].map((label) => (
        <Stack orientation="horizontal" gap={3} key={label}>
          <SkeletonPlaceholder aria-hidden="true" style={{ width: "1rem", height: "1rem" }} />
          <span className="cds--type-body-01">{label}</span>
        </Stack>
      ))}
    </>
  );
}
