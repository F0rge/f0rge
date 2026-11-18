"use client";

import { SkeletonPlaceholder, SkeletonText, Stack } from "@carbon/react";
import { LoadingField, LoadingRegion } from "@/components/page-loading";
import { REMINDER_PLACEHOLDER_HELP } from "@/lib/payment-reminders";
import styles from "./settings.module.css";

function Fields({ labels }: { labels: readonly string[] }) {
  return labels.map((label) => <LoadingField key={label} label={label} />);
}

export function SettingsPanelLoading({ panel }: { panel: "Company" | "Documents" | "Locations" | "Operations" | "Labels" }) {
  return (
    <LoadingRegion label={`Loading ${panel.toLowerCase()} settings…`}>
      <Stack gap={5}>
        <h2 className="cds--type-heading-03">{panel}</h2>
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
            <p className="cds--type-body-01 firstout-muted-text">
              Prefix and padding apply to new documents. Cancelled documents keep their numbers — next value only advances on allocation.
            </p>
            <div className="firstout-settings-sequences">
              <div className="firstout-settings-sequences__header cds--type-label-01">
                <span>Document type</span><span>Prefix</span><span>Padding</span><span>Next value</span>
              </div>
              {Array.from({ length: 4 }, (_, index) => (
                <div key={index} className="firstout-settings-sequences__row" aria-hidden="true">
                  <SkeletonText width="70%" />
                  <LoadingSkeleton />
                  <LoadingSkeleton />
                  <LoadingSkeleton />
                </div>
              ))}
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

function LoadingSkeleton() {
  return <SkeletonPlaceholder style={{ width: "100%", height: "2.5rem" }} />;
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

export function CommunicationsLoading() {
  return (
    <LoadingRegion label="Loading communications…">
      <Stack gap={5}>
        <div>
          <h2 className="cds--type-productive-heading-03">Communications</h2>
          <p className="cds--type-body-01 firstout-muted-text">
            Use the mailbox your ISP or Microsoft 365 gave you (SMTP). This is not Gmail API.
          </p>
        </div>
        <Fields labels={["SMTP host", "Port", "Security", "Username", "Password", "From address", "From name", "Reply-To", "Test send to"]} />
        <div>
          <h3 className="cds--type-productive-heading-02">WhatsApp Cloud API</h3>
          <p className="cds--type-body-01 firstout-muted-text">
            Keep the WhatsApp Business app on this number. Paste the Cloud API token here; we do not replace the Business app. Unofficial WhatsApp libraries are not used.
          </p>
          <SkeletonText width="70%" aria-hidden="true" />
        </div>
        <Fields labels={["Phone number ID", "Business account ID", "Access token", "App secret", "Utility template name", "Template language"]} />
      </Stack>
    </LoadingRegion>
  );
}

export function PaymentRemindersLoading() {
  return (
    <LoadingRegion label="Loading payment reminders…">
      <Stack gap={5}>
        <div>
          <h2 className="cds--type-productive-heading-03">Payment reminders</h2>
          <p className="cds--type-body-01 firstout-muted-text">
            Off until you turn them on. Firstout emails one reminder per invoice each day the job runs, using the outstanding balance, and stops when the invoice is paid.
          </p>
        </div>
        <ToggleLoading label="Send payment reminders" />
        <p className="cds--type-helper-text-01">{REMINDER_PLACEHOLDER_HELP}</p>
        <Stack gap={3}>
          <LoadingField label="Step 1 — day offset" />
          <LoadingField label="Subject" />
          <LoadingField label="Email" height="9rem" />
        </Stack>
      </Stack>
    </LoadingRegion>
  );
}
