"use client";

import { Button, InlineNotification, Select, SelectItem, Stack, Tag, TextInput, Tile } from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  createProductGroup, listProductGroups, listSkus, replaceProductGroupVariants,
  updateProductGroup, updateSku, type ProductGroup, type ProductGroupVariantWrite, type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canMutateCatalogue } from "@/lib/permissions";

type Axis = { name: string; values: string };
type VariantRow = { source_sku_id: string; options: Record<string, string> };
const blankRow = (): VariantRow => ({ source_sku_id: "", options: {} });

function axesFromGroup(group: ProductGroup): Axis[] {
  return Object.entries(group.options).map(([name, values]) => ({ name, values: values.join(", ") }));
}

function optionMap(axes: Axis[]): Record<string, string[]> {
  return Object.fromEntries(axes.map(({ name, values }) => [name.trim(), values.split(",").map((value) => value.trim()).filter(Boolean)]));
}

function issues(title: string, options: Record<string, string[]>, rows: VariantRow[]): string[] {
  const problems: string[] = [];
  if (!title.trim()) problems.push("Enter a product title.");
  const names = Object.keys(options);
  if (!names.length || names.some((name) => !name)) problems.push("Name each option, such as Colour or Size.");
  if (new Set(names.map((name) => name.toLowerCase())).size !== names.length) problems.push("Option names must be unique.");
  if (Object.values(options).some((values) => !values.length || new Set(values.map((value) => value.toLowerCase())).size !== values.length)) problems.push("Give each option distinct values.");
  if (rows.length < 2) problems.push("Map at least two existing SKUs.");
  const ids = rows.map((row) => row.source_sku_id);
  if (ids.some((id) => !id)) problems.push("Select a SKU for every variant.");
  if (new Set(ids).size !== ids.length) problems.push("A SKU can appear only once in this product.");
  if (rows.some((row) => names.some((name) => !options[name].includes(row.options[name])))) problems.push("Assign a valid value for every option on every SKU.");
  const keys = rows.map((row) => JSON.stringify(names.map((name) => row.options[name])));
  if (new Set(keys).size !== keys.length) problems.push("Each option combination must identify one SKU.");
  return problems;
}

export default function ProductGroupsPage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [groups, setGroups] = useState<ProductGroup[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [axes, setAxes] = useState<Axis[]>([{ name: "Colour", values: "" }]);
  const [rows, setRows] = useState<VariantRow[]>([blankRow(), blankRow()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const selected = groups.find((group) => group.id === selectedId);
  const options = optionMap(axes);
  const validation = issues(title, options, rows);
  const duplicateAxisNames = new Set(axes.map((axis) => axis.name.trim().toLowerCase())).size !== axes.length;
  if (duplicateAxisNames) validation.push("Option names must be unique.");
  const unapproved = rows.filter((row) => { const sku = skus.find((item) => item.id === row.source_sku_id); return sku && !sku.storefront_published; });
  const withoutPrice = rows.filter((row) => { const sku = skus.find((item) => item.id === row.source_sku_id); return sku && (!sku.retail_inc_vat || Number(sku.retail_inc_vat) <= 0); });
  const unsavedChanges = !!selected && (title.trim() !== selected.title || JSON.stringify(rows) !== JSON.stringify(selected.variants.map(({ source_sku_id, options }) => ({ source_sku_id, options }))));
  const readyForSource = validation.length === 0 && unapproved.length === 0 && withoutPrice.length === 0 && !unsavedChanges;

  const refresh = useCallback(async () => {
    try {
      const [nextGroups, nextSkus] = await Promise.all([listProductGroups(), listSkus()]);
      setGroups(nextGroups); setSkus(nextSkus);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load product groups."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (user) void refresh(); }, [user, refresh]);

  function openGroup(group: ProductGroup) {
    setSelectedId(group.id); setTitle(group.title); setAxes(axesFromGroup(group));
    setRows(group.variants.map(({ source_sku_id, options }) => ({ source_sku_id, options })));
    setError(null); setMessage(null);
  }
  function startNew() {
    setSelectedId(null); setTitle(""); setAxes([{ name: "Colour", values: "" }]);
    setRows([blankRow(), blankRow()]); setError(null); setMessage(null);
  }
  function updateRow(index: number, patch: Partial<VariantRow>) {
    setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row));
  }
  async function save() {
    if (!canMutate || validation.length) return;
    setSaving(true); setError(null); setMessage(null);
    const variants: ProductGroupVariantWrite[] = rows.map((row) => ({ source_sku_id: row.source_sku_id, options: row.options }));
    try {
      const group = selectedId
        ? await updateProductGroup(selectedId, { title: title.trim() })
        : await createProductGroup({ title: title.trim(), options, variants });
      if (selectedId) await replaceProductGroupVariants(group.id, variants);
      await refresh(); setSelectedId(group.id); setMessage("Product group saved. Check the publication steps below.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save product group."); }
    finally { setSaving(false); }
  }
  async function enableSku(id: string) {
    setSaving(true); setError(null);
    try { await updateSku(id, { storefront_published: true }); await refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not enable SKU for the storefront."); }
    finally { setSaving(false); }
  }
  async function setPublished(published: boolean) {
    if (!selectedId || (published && !readyForSource)) return;
    setSaving(true); setError(null); setMessage(null);
    try {
      await updateProductGroup(selectedId, { storefront_published: published });
      await refresh(); setMessage(published ? "Group enabled for commerce sync. Finish the public merchandising checks in Medusa before publishing." : "Group removed from commerce sync.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not change publication status."); }
    finally { setSaving(false); }
  }

  return <Stack gap={6}>
    <div className="firstout-page-header"><div><h1 className="cds--type-productive-heading-04">Storefront products</h1><p className="cds--type-body-01">Group operational SKUs into one product with explicit shopper options.</p></div><Button onClick={startNew} disabled={!canMutate}>New product group</Button></div>
    {error && <InlineNotification kind="error" title="Error" subtitle={error} onCloseButtonClick={() => setError(null)} lowContrast />}
    {message && <InlineNotification kind="success" title="Updated" subtitle={message} onCloseButtonClick={() => setMessage(null)} lowContrast />}
    {loading ? <p>Loading product groups…</p> : <div className="firstout-detail-grid">
      <Tile><h2 className="cds--type-productive-heading-03">Products</h2>{groups.length === 0 && <p>No product groups yet.</p>}{groups.map((group) => <div key={group.id} style={{ marginTop: "1rem" }}><Button kind="ghost" onClick={() => openGroup(group)}>{group.title}</Button> <Tag type={group.storefront_published ? "green" : "gray"}>{group.storefront_published ? "Sync enabled" : "Draft"}</Tag><p>{group.variants.length} variants</p></div>)}</Tile>
      <Tile><Stack gap={5}><h2 className="cds--type-productive-heading-03">{selected ? "Edit product group" : "New product group"}</h2>
        <TextInput id="group-title" labelText="Shopper product title" value={title} readOnly={!canMutate} onChange={(event) => setTitle(event.target.value)} />
        <h3 className="cds--type-productive-heading-02">Options</h3>
        {axes.map((axis, index) => <div key={index} className="firstout-detail-grid"><TextInput id={`option-name-${index}`} labelText={`Option ${index + 1} name`} value={axis.name} readOnly={!canMutate || !!selected} onChange={(event) => setAxes((items) => items.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} /><TextInput id={`option-values-${index}`} labelText="Values, separated by commas" value={axis.values} readOnly={!canMutate || !!selected} onChange={(event) => setAxes((items) => items.map((item, i) => i === index ? { ...item, values: event.target.value } : item))} /></div>)}
        {!selected && canMutate && axes.length < 3 && <Button kind="tertiary" size="sm" onClick={() => setAxes((items) => [...items, { name: "", values: "" }])}>Add option</Button>}
        <h3 className="cds--type-productive-heading-02">SKU variants</h3>
        {rows.map((row, index) => <div key={index} style={{ borderTop: "1px solid #d8d8d8", paddingTop: "1rem" }}><Stack gap={3}><Select id={`variant-sku-${index}`} labelText={`Variant ${index + 1} SKU`} value={row.source_sku_id} disabled={!canMutate} onChange={(event) => updateRow(index, { source_sku_id: event.target.value })}><SelectItem value="" text="Select an existing SKU" />{skus.map((sku) => <SelectItem key={sku.id} value={sku.id} text={`${sku.our_ref} — ${sku.name}`} />)}</Select>{Object.entries(options).map(([name, values]) => <Select key={name} id={`variant-${index}-${name}`} labelText={name || "Option value"} value={row.options[name] || ""} disabled={!canMutate} onChange={(event) => updateRow(index, { options: { ...row.options, [name]: event.target.value } })}><SelectItem value="" text="Select a value" />{values.map((value) => <SelectItem key={value} value={value} text={value} />)}</Select>)}{rows.length > 2 && canMutate && <Button kind="danger--tertiary" size="sm" onClick={() => setRows((items) => items.filter((_, i) => i !== index))}>Remove variant</Button>}</Stack></div>)}
        {canMutate && <Button kind="tertiary" size="sm" onClick={() => setRows((items) => [...items, blankRow()])}>Add SKU variant</Button>}
        {validation.length > 0 && <div role="status"><h3 className="cds--type-productive-heading-02">To save</h3><ul>{validation.map((problem) => <li key={problem}>{problem}</li>)}</ul></div>}
        {canMutate && <Button disabled={saving || validation.length > 0} onClick={() => void save()}>{saving ? "Saving…" : "Save product group"}</Button>}
        {selected && <div><h3 className="cds--type-productive-heading-02">Publication readiness</h3><p>Firstout sends operational identity, VAT-inclusive price and availability to Medusa. Medusa publication also needs useful copy, dimensions, materials, care instructions and at least three suitable public photos per variant.</p>{unsavedChanges && <p>Save your group changes before enabling commerce sync.</p>}{withoutPrice.length > 0 && <p>{withoutPrice.length} mapped SKU(s) need a positive VAT-inclusive retail price.</p>}{unapproved.length > 0 && <div><p>{unapproved.length} mapped SKU(s) still need storefront opt-in.</p>{unapproved.map((row) => { const sku = skus.find((item) => item.id === row.source_sku_id); return sku && <Button key={sku.id} kind="tertiary" size="sm" disabled={!canMutate || saving} onClick={() => void enableSku(sku.id)}>Enable {sku.our_ref}</Button>; })}</div>}{canMutate && <Button kind={selected.storefront_published ? "danger--tertiary" : "secondary"} disabled={saving || (!selected.storefront_published && !readyForSource)} onClick={() => void setPublished(!selected.storefront_published)}>{selected.storefront_published ? "Disable commerce sync" : "Enable commerce sync"}</Button>}</div>}
      </Stack></Tile>
    </div>}
  </Stack>;
}
