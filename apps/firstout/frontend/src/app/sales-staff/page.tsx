"use client";

import { ArrowRight, UserFollow } from "@carbon/icons-react";
import {
  Button, DataTableSkeleton, InlineNotification, Modal, OverflowMenu, OverflowMenuItem, SkeletonText, Stack,
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag, TextInput, Toggle,
} from "@carbon/react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AdminPageHeader } from "@/components/administration";
import { PageLoading } from "@/components/page-loading";
import metrics from "@/components/staff-metrics.module.css";
import {
  ApiError, can, createSalesStaff, deleteSalesStaff, getCommissionReport, listSalesStaff, updateSalesStaff,
  type SalesStaff,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { recentMonths, zar } from "@/lib/sales-staff";
import styles from "../users/users.module.css";

type View = "active" | "inactive" | "all";

const message = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback);

function ColleagueModal({
  person, onClose, onSaved,
}: { person: SalesStaff | null; onClose: () => void; onSaved: (saved: SalesStaff, created: boolean) => void }) {
  const [name, setName] = useState(person?.name ?? "");
  const [shortName, setShortName] = useState(person?.short_name ?? "");
  const [rate, setRate] = useState(person ? String(Number(person.commission_rate)) : "0");
  const [active, setActive] = useState(person?.is_active ?? true);
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const rateNumber = Number(rate);
  const nameError = !name.trim() ? "Enter the colleague's name." : "";
  const rateError = rate.trim() === "" || !(rateNumber >= 0 && rateNumber <= 100) ? "Enter a rate from 0 to 100." : "";

  async function save() {
    setTried(true);
    if (nameError || rateError || saving) return;
    setSaving(true);
    setError("");
    const payload = {
      name: name.trim(), short_name: shortName.trim() || null,
      commission_rate: rateNumber.toFixed(2), is_active: active,
    };
    try {
      onSaved(person ? await updateSalesStaff(person.id, payload) : await createSalesStaff(payload), !person);
    } catch (err) {
      setError(message(err, "Could not save the colleague."));
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      modalHeading={person ? "Edit colleague" : "Add colleague"}
      modalLabel="Sales staff aren't logins. The till asks who made each sale."
      primaryButtonText={saving ? "Saving…" : "Save"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving}
      onRequestSubmit={() => void save()}
      onRequestClose={onClose}
    >
      <Stack gap={5}>
        {error && <InlineNotification lowContrast kind="error" title="Not saved" subtitle={error} hideCloseButton />}
        <TextInput id="sales-staff-name" labelText="Full name" value={name} maxLength={120}
          invalid={tried && !!nameError} invalidText={nameError} onChange={(event) => setName(event.target.value)} />
        <TextInput id="sales-staff-short" labelText="Short name shown on the till and documents" value={shortName}
          maxLength={32} placeholder={name.trim().split(/\s+/)[0] || ""} helperText="Leave blank to use the first name."
          onChange={(event) => setShortName(event.target.value)} />
        <TextInput id="sales-staff-rate" labelText="Commission rate (%)" type="number" min={0} max={100} step={0.01}
          value={rate} invalid={tried && !!rateError} invalidText={rateError}
          helperText="Applied to commissionable sales excl. VAT." onChange={(event) => setRate(event.target.value)} />
        <Toggle id="sales-staff-active" labelText="Status" labelA="Inactive" labelB="Active" toggled={active}
          onToggle={setActive} />
        <p className="cds--type-helper-text-01">
          Inactive colleagues disappear from the till. Their past sales stay in the commission report.
        </p>
      </Stack>
    </Modal>
  );
}

function SalesStaffScreen() {
  const [view, setView] = useState<View>("active");
  const [editing, setEditing] = useState<SalesStaff | "new" | null>(null);
  const [deleting, setDeleting] = useState<SalesStaff | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [month] = useState(() => recentMonths()[0]);

  const client = useQueryClient();
  const directory = useQuery({
    queryKey: ["sales-staff", "directory", month.value],
    queryFn: async () => {
      const [rows, monthReport] = await Promise.all([
        listSalesStaff("all"),
        // The tile is a convenience: the directory still works without it.
        getCommissionReport(month.value).catch(() => null),
      ]);
      return { rows, monthReport };
    },
  });
  const staff = directory.data?.rows ?? null;
  const report = directory.data?.monthReport ?? null;
  // A retry clears the message while it runs, as before.
  const loadError = directory.error && !directory.isFetching ? message(directory.error, "Could not load sales staff.") : "";
  // Also refreshes the till's colleague options.
  const load = () => client.invalidateQueries({ queryKey: ["sales-staff"] });

  const active = staff?.filter((item) => item.is_active) ?? [];
  const inactive = staff?.filter((item) => !item.is_active) ?? [];
  const rows = view === "active" ? active : view === "inactive" ? inactive : staff ?? [];
  const monthSales = (id: string) => report?.rows.find((row) => row.sales_staff_id === id)?.commissionable_ex_vat;
  const monthTotal = report?.rows.reduce((sum, row) => sum + Number(row.commissionable_ex_vat), 0);

  async function setStatus(person: SalesStaff, on: boolean) {
    setError("");
    try {
      await updateSalesStaff(person.id, { is_active: on });
      setNotice(on ? `${person.name} is back on the till.` : `${person.name} no longer appears on the till. Past sales are kept.`);
      await load();
    } catch (err) {
      setError(message(err, "Could not change the colleague's status."));
    }
  }

  async function remove(person: SalesStaff) {
    setError("");
    try {
      await deleteSalesStaff(person.id);
      setNotice(`${person.name} deleted.`);
      await load();
    } catch (err) {
      setError(message(err, "Could not delete the colleague."));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <Stack gap={5} className={styles.page}>
      <AdminPageHeader
        title="Sales staff"
        description="The people who make sales. They don't need a login: colleagues can share one till account, and the till asks who made each sale."
      >
        <Button renderIcon={UserFollow} onClick={() => setEditing("new")}>Add colleague</Button>
      </AdminPageHeader>
      <dl aria-label="Sales staff summary" className={metrics.metrics}>
        <div className={metrics.metric}>
          <dt>Active colleagues</dt>
          <dd>{staff ? active.length : <SkeletonText width="2rem" />}</dd>
        </div>
        <div className={metrics.metric}>
          <dt>Inactive</dt>
          <dd>{staff ? inactive.length : <SkeletonText width="2rem" />}</dd>
        </div>
        <div className={metrics.metric}>
          <dt>Commissionable sales this month</dt>
          <dd>{monthTotal === undefined ? (staff ? "—" : <SkeletonText width="4rem" />) : zar(monthTotal)}</dd>
          <dd className={metrics.capacityNote}>Excl. VAT, {month.label}</dd>
        </div>
      </dl>
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {error && <InlineNotification lowContrast kind="error" title="Not changed" subtitle={error} onCloseButtonClick={() => setError("")} />}
      <section aria-labelledby="sales-staff-title" className={styles.directory}>
        <h2 id="sales-staff-title" className={styles.sectionTitle}>Sales colleagues</h2>
        <p className={`${styles.controls} cds--type-body-01`}>
          Team members manage logins. Sales colleagues are only used to attribute sales and commission.
          <Link href="/users">Go to Team members</Link>
        </p>
        <div className={styles.controls}>
          <div role="group" aria-label="Colleague status" className={styles.actions}>
            {([["active", "Active", active.length], ["inactive", "Inactive", inactive.length], ["all", "All", null]] as const).map(
              ([value, label, count]) => (
                <Button key={value} size="sm" kind={view === value ? "tertiary" : "ghost"} aria-pressed={view === value}
                  onClick={() => setView(value)}>
                  {label}{staff && count !== null ? ` (${count})` : ""}
                </Button>
              ),
            )}
          </div>
          {staff && <p role="status">{rows.length} {rows.length === 1 ? "colleague" : "colleagues"}</p>}
        </div>
        {loadError ? (
          <div className={styles.feedback}>
            <InlineNotification lowContrast kind="error" title="Could not load sales staff" subtitle={loadError} hideCloseButton />
            <Button size="sm" kind="tertiary" onClick={() => void load()}>Retry</Button>
          </div>
        ) : !staff ? (
          <DataTableSkeleton aria-label="Loading sales staff" columnCount={5} rowCount={3} showHeader={false} showToolbar={false} />
        ) : rows.length === 0 ? (
          <p role="status" className={styles.empty}>
            {view === "inactive" ? "No inactive colleagues." : "No sales colleagues yet. Add the people who make sales."}
          </p>
        ) : (
          <div className={styles.tableScroll} role="region" aria-label="Sales colleagues table" tabIndex={0}>
            <Table size="lg" aria-label="Sales colleagues">
              <TableHead>
                <TableRow>
                  <TableHeader>Sales colleague</TableHeader>
                  <TableHeader>Commission rate</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Sales this month</TableHeader>
                  <TableHeader>Since</TableHeader>
                  <TableHeader><span className="cds--visually-hidden">Actions</span></TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((person) => (
                  <TableRow key={person.id}>
                    <TableCell>
                      <button type="button" className={styles.memberLink} onClick={() => setEditing(person)}>
                        {person.name}
                        <ArrowRight size={14} aria-hidden="true" />
                      </button>
                      {person.short_name && <small className={styles.email}>Shown as {person.short_name}</small>}
                    </TableCell>
                    <TableCell>{Number(person.commission_rate)}%</TableCell>
                    <TableCell>
                      <Tag size="sm" type={person.is_active ? "green" : "gray"}>{person.is_active ? "Active" : "Inactive"}</Tag>
                    </TableCell>
                    <TableCell>{report ? zar(monthSales(person.id) ?? 0) : "—"}</TableCell>
                    <TableCell>{person.created_at.slice(0, 10)}</TableCell>
                    <TableCell>
                      <OverflowMenu aria-label={"Actions for " + person.name} iconDescription={"Actions for " + person.name} flipped size="sm">
                        <OverflowMenuItem itemText="Edit" onClick={() => setEditing(person)} />
                        <OverflowMenuItem
                          itemText={person.is_active ? "Deactivate" : "Reactivate"}
                          onClick={() => void setStatus(person, !person.is_active)}
                        />
                        <OverflowMenuItem itemText="Delete" isDelete hasDivider onClick={() => setDeleting(person)} />
                      </OverflowMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
      <div>
        <InlineNotification
          lowContrast
          hideCloseButton
          kind="info"
          title="How commission works"
          subtitle="Worked out on the sale excluding VAT, after discounts. Products with Exclude from commission ticked on their Prices tab, such as delivery and installation, are left out. A sale counts in the month its invoice is issued; credit notes deduct in the month they're issued."
        />
        <Link href="/commission">Open the commission report</Link>
      </div>
      {editing && (
        <ColleagueModal
          key={editing === "new" ? "new" : editing.id}
          person={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved, created) => {
            setEditing(null);
            setNotice(`${saved.name} ${created ? "added" : "updated"}. ${saved.is_active ? "Shown" : "Not shown"} on the till.`);
            void load();
          }}
        />
      )}
      {deleting && (
        <Modal
          open
          danger
          size="sm"
          modalHeading={`Delete ${deleting.name}?`}
          primaryButtonText="Delete"
          secondaryButtonText="Cancel"
          onRequestSubmit={() => void remove(deleting)}
          onRequestClose={() => setDeleting(null)}
        >
          <p>
            Only colleagues with no invoices or quotes can be deleted. Otherwise deactivate them so their sales stay
            attributed. This can&apos;t be undone.
          </p>
        </Modal>
      )}
    </Stack>
  );
}

export default function SalesStaffPage() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoading label="Loading sales staff…" />;
  if (!user || !can(user, "users.manage")) {
    return <InlineNotification kind="error" title="Access denied" subtitle="Staff management permission is required." hideCloseButton />;
  }
  return <SalesStaffScreen />;
}
