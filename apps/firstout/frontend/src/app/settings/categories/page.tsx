"use client";

import { Add } from "@carbon/icons-react";
import {
  Button, DataTableSkeleton, InlineNotification, Link, Modal, OverflowMenu, OverflowMenuItem, Select, SelectItem,
  Stack, Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag, TextInput,
} from "@carbon/react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AdminPageHeader } from "@/components/administration";
import { useCategories } from "@/components/catalogue-lists/hooks";
import { PageLoading } from "@/components/page-loading";
import { ApiError, can } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FALLBACK_SALES_CODE, flattenCategoryTree } from "@/lib/catalogue-list-view";
import {
  createCategory, updateCategory, type Category, type ListLifecycle, type ShopSection,
} from "@/lib/catalogue-lists";
import { queryKeys } from "@/lib/queries";
import styles from "../../users/users.module.css";
import own from "../catalogue-lists.module.css";

const message = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback);

type Editing = { kind: "add"; parent: Category | null } | { kind: "rename"; category: Category };

function CategoryModal({
  editing, sections, onClose, onSaved,
}: { editing: Editing; sections: ShopSection[]; onClose: () => void; onSaved: (saved: Category) => void }) {
  const renaming = editing.kind === "rename" ? editing.category : null;
  const parent = editing.kind === "add" ? editing.parent : null;
  const [name, setName] = useState(renaming?.name ?? "");
  const [section, setSection] = useState("");
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const nameError = !name.trim() ? "Enter a name." : "";
  const what = renaming ? (renaming.parent_id ? "sub-category" : "category") : parent ? "sub-category" : "category";

  async function save() {
    setTried(true);
    if (nameError || saving) return;
    setSaving(true);
    setError("");
    try {
      onSaved(renaming
        ? await updateCategory(renaming.id, { name: name.trim() })
        : await createCategory({ name: name.trim(), parent_id: parent?.id ?? null, shop_category: !parent && section ? section : null }));
    } catch (err) {
      setError(message(err, `Could not save the ${what}.`));
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      size="sm"
      modalHeading={renaming ? `Rename ${renaming.name}` : parent ? `Add a sub-category to ${parent.name}` : "Add category"}
      modalLabel={renaming && !renaming.parent_id ? "SKUs and category posting follow the new name." : undefined}
      primaryButtonText={saving ? "Saving…" : "Save"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving}
      onRequestSubmit={() => void save()}
      onRequestClose={onClose}
    >
      <Stack gap={5}>
        {error && <InlineNotification lowContrast kind="error" title="Not saved" subtitle={error} hideCloseButton />}
        <TextInput id="category-name" labelText="Name" value={name} maxLength={64} data-modal-primary-focus
          invalid={tried && !!nameError} invalidText={nameError} onChange={(event) => setName(event.target.value)} />
        {editing.kind === "add" && !parent && (
          <Select id="category-shop-section" labelText="Shop section" value={section}
            helperText="Where the DasKasas shop lists this category's pieces. Leave it out to keep them off the shop."
            onChange={(event) => setSection(event.target.value)}>
            <SelectItem value="" text="Not on the shop" />
            {sections.map((entry) => <SelectItem key={entry.slug} value={entry.slug} text={entry.label} />)}
          </Select>
        )}
      </Stack>
    </Modal>
  );
}

function SalesAccountCell({ row }: { row: Category }) {
  if (row.parent_id) return <span className={styles.email}>Posts with its category</span>;
  if (row.sales_account) return <>{row.sales_account.code} {row.sales_account.name}</>;
  return (
    <span className={own.unmapped}>
      <Tag size="sm" type="warm-gray">Not mapped</Tag>
      <span>Posts to the {FALLBACK_SALES_CODE} fallback.</span>
      <Link href="/ledger?posting=1" size="sm">Set up category posting</Link>
    </span>
  );
}

function CategoriesScreen({ canMutate }: { canMutate: boolean }) {
  const [view, setView] = useState<ListLifecycle>("active");
  const [editing, setEditing] = useState<Editing | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const client = useQueryClient();
  const tree = useCategories(view);
  const categories = tree.data?.categories ?? null;
  const sections = tree.data?.shop_sections ?? [];
  const rows = categories ? flattenCategoryTree(categories) : [];
  const loadError = tree.error && !tree.isFetching ? message(tree.error, "Could not load categories.") : "";
  const sectionLabel = (slug: string | null) => sections.find((entry) => entry.slug === slug)?.label ?? slug;

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["categories"] }),
    // A rename rewrites SKU category names and the ledger's posting entry.
    client.invalidateQueries({ queryKey: queryKeys.skus }),
    client.invalidateQueries({ queryKey: ["ledger"] }),
  ]);

  async function change(category: Category, payload: Parameters<typeof updateCategory>[1], done: string) {
    setError("");
    setNotice("");
    try {
      await updateCategory(category.id, payload);
      setNotice(done);
      await refresh();
    } catch (err) {
      setError(message(err, `Could not change ${category.name}.`));
    }
  }

  return (
    <Stack gap={5} className={styles.page}>
      <AdminPageHeader
        title="Categories"
        description="Every SKU belongs to one category and, optionally, one of its sub-categories. The category decides the ledger accounts a sale posts to and the shop section it appears in."
      >
        {canMutate && <Button renderIcon={Add} onClick={() => setEditing({ kind: "add", parent: null })}>Add category</Button>}
      </AdminPageHeader>
      {!canMutate && (
        <InlineNotification lowContrast hideCloseButton kind="info" title="View only"
          subtitle="Changing categories needs the “Edit the catalogue” permission." />
      )}
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {error && <InlineNotification lowContrast kind="error" title="Not changed" subtitle={error} onCloseButtonClick={() => setError("")} />}
      <section aria-labelledby="categories-title" className={styles.directory}>
        <h2 id="categories-title" className={styles.sectionTitle}>Categories and sub-categories</h2>
        <div className={styles.controls}>
          <div role="group" aria-label="Category status" className={styles.actions}>
            {([["active", "Active"], ["archived", "Archived"], ["all", "All"]] as const).map(([value, label]) => (
              <Button key={value} size="sm" kind={view === value ? "tertiary" : "ghost"} aria-pressed={view === value}
                onClick={() => setView(value)}>{label}</Button>
            ))}
          </div>
          {categories && <p role="status">{categories.length} {categories.length === 1 ? "category" : "categories"}</p>}
        </div>
        {loadError ? (
          <div className={styles.feedback}>
            <InlineNotification lowContrast kind="error" title="Could not load categories" subtitle={loadError} hideCloseButton />
            <Button size="sm" kind="tertiary" onClick={() => void tree.refetch()}>Retry</Button>
          </div>
        ) : !categories ? (
          <DataTableSkeleton aria-label="Loading categories" columnCount={5} rowCount={4} showHeader={false} showToolbar={false} />
        ) : rows.length === 0 ? (
          <p role="status" className={styles.empty}>
            {view === "archived" ? "No archived categories." : "No categories yet. Add the groupings your SKUs fall into."}
          </p>
        ) : (
          <div className={styles.tableScroll} role="region" aria-label="Categories table" tabIndex={0}>
            <Table size="md" aria-label="Categories">
              <TableHead>
                <TableRow>
                  <TableHeader>Name</TableHeader>
                  <TableHeader>Sales account</TableHeader>
                  <TableHeader>Shop section</TableHeader>
                  <TableHeader>SKUs</TableHeader>
                  <TableHeader>Status</TableHeader>
                  {canMutate && <TableHeader><span className="cds--visually-hidden">Actions</span></TableHeader>}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map(({ category: row, parent }) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <span className={parent ? own.child : own.parent}>
                        {parent && <span className="cds--visually-hidden">Sub-category of {parent.name}: </span>}
                        {row.name}
                      </span>
                    </TableCell>
                    <TableCell><SalesAccountCell row={row} /></TableCell>
                    <TableCell>
                      {parent ? (
                        <span className={styles.email}>—</span>
                      ) : canMutate && !row.is_archived ? (
                        <Select id={`shop-section-${row.id}`} labelText={`Shop section for ${row.name}`} hideLabel size="sm"
                          value={row.shop_category ?? ""}
                          onChange={(event) => void change(row, { shop_category: event.target.value || null },
                            event.target.value ? `${row.name} now shows in ${sectionLabel(event.target.value)} on the shop.` : `${row.name} is no longer on the shop.`)}>
                          <SelectItem value="" text="Not on the shop" />
                          {row.shop_category && !sections.some((entry) => entry.slug === row.shop_category) && (
                            <SelectItem value={row.shop_category} text={row.shop_category} />
                          )}
                          {sections.map((entry) => <SelectItem key={entry.slug} value={entry.slug} text={entry.label} />)}
                        </Select>
                      ) : (
                        sectionLabel(row.shop_category) ?? "Not on the shop"
                      )}
                    </TableCell>
                    <TableCell>{row.sku_count}</TableCell>
                    <TableCell>
                      <Tag size="sm" type={row.is_archived ? "gray" : "green"}>{row.is_archived ? "Archived" : "Active"}</Tag>
                    </TableCell>
                    {canMutate && (
                      <TableCell>
                        <OverflowMenu aria-label={`Actions for ${row.name}`} iconDescription={`Actions for ${row.name}`} flipped size="sm">
                          <OverflowMenuItem itemText="Rename" onClick={() => setEditing({ kind: "rename", category: row })} />
                          {!parent && !row.is_archived && (
                            <OverflowMenuItem itemText="Add sub-category" onClick={() => setEditing({ kind: "add", parent: row })} />
                          )}
                          {row.is_archived ? (
                            <OverflowMenuItem itemText="Restore" onClick={() => void change(row, { is_archived: false }, `${row.name} restored.`)} />
                          ) : (
                            <OverflowMenuItem itemText="Archive" hasDivider isDelete
                              onClick={() => void change(row, { is_archived: true },
                                !parent && row.subcategories.some((sub) => !sub.is_archived)
                                  ? `${row.name} and its sub-categories archived.` : `${row.name} archived.`)} />
                          )}
                        </OverflowMenu>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
      <p className="cds--type-helper-text-01">
        Archived categories stay on the SKUs that already have them but can&apos;t be chosen for new ones. A category in use by active SKUs can&apos;t be archived.
      </p>
      {editing && (
        <CategoryModal
          key={editing.kind === "rename" ? editing.category.id : `add-${editing.parent?.id ?? "top"}`}
          editing={editing}
          sections={sections}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            setNotice(editing.kind === "rename" ? `Renamed to ${saved.name}.` : `${saved.name} added.`);
            void refresh();
          }}
        />
      )}
    </Stack>
  );
}

export default function CategoriesPage() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoading label="Loading categories…" />;
  if (!user) return null;
  return <CategoriesScreen canMutate={can(user, "catalogue.mutate")} />;
}
