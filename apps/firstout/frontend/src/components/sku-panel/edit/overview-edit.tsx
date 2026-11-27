"use client";

import { TextInput, Toggle } from "@carbon/react";
import { CategoryPicker } from "@/components/catalogue-lists/category-picker";
import { useCategories, useMaterials } from "@/components/catalogue-lists/hooks";
import { MaterialPicker } from "@/components/catalogue-lists/material-picker";
import { SkuProductDetailsFields } from "@/components/sku-product-details-fields";
import { updateSku } from "@/lib/api";
import { overviewFormFromSku, overviewPayload, validateOverview, type OverviewForm } from "@/lib/catalogue-editor";
import type { SkuOverview } from "@/lib/catalogue-lists";
import { CardForm, useCardDraft } from "./shared";
import styles from "../sku-panel.module.css";

export function OverviewEdit({ overview }: { overview: SkuOverview }) {
  const { sku } = overview;
  const card = useCardDraft(sku.id, () => overviewFormFromSku(sku));
  const { draft, update, errors } = card;
  const categories = useCategories();
  const materials = useMaterials();
  const materialNames = Object.fromEntries([sku.main_material, ...sku.other_materials].flatMap((item) => (item ? [[item.id, item.name]] : [])));
  const text = (field: keyof OverviewForm & ("our_ref" | "our_barcode" | "name" | "design"), label: string, wide = false) => (
    <div className={wide ? styles.editWide : undefined}>
      <TextInput
        id={`sku-edit-${field}`}
        labelText={label}
        value={draft[field]}
        invalid={Boolean(errors[field])}
        invalidText={errors[field]}
        disabled={card.saving}
        onChange={(event) => update({ [field]: event.target.value })}
      />
    </div>
  );
  const save = () => void card.save(validateOverview(draft), () => {
    const payload = overviewPayload(sku, draft);
    return Object.keys(payload).length ? updateSku(sku.id, payload) : Promise.resolve(null);
  });

  return (
    <CardForm id="overview" saving={card.saving} failure={card.failure} onSave={save}>
      <div className={styles.editGrid}>
        {text("our_ref", "Our ref")}
        {text("our_barcode", "Our barcode")}
        {text("name", "Name", true)}
        {text("design", "Design", true)}
        <div className={styles.editWide}>
          <CategoryPicker
            idPrefix="sku-edit"
            categories={categories.data?.categories}
            value={{ categoryId: draft.category_id, subcategoryId: draft.subcategory_id }}
            onChange={(next) => update({ category_id: next.categoryId, subcategory_id: next.subcategoryId })}
            disabled={card.saving}
            invalidText={{ category: errors.category_id, subcategory: errors.subcategory_id }}
            fallbackNames={{ category: sku.category, subcategory: sku.subcategory }}
          />
        </div>
        <div className={styles.editWide}>
          <MaterialPicker
            idPrefix="sku-edit"
            materials={materials.data}
            value={{ mainId: draft.main_material_id, otherIds: draft.other_material_ids }}
            onChange={(next) => update({ main_material_id: next.mainId, other_material_ids: next.otherIds })}
            disabled={card.saving}
            invalidText={{ main: errors.main_material_id, others: errors.other_material_ids }}
            fallbackNames={materialNames}
          />
        </div>
        <div className={styles.editWide}>
          <SkuProductDetailsFields
            idPrefix="sku-edit"
            form={draft}
            errors={errors}
            disabled={card.saving}
            onChange={(field, value) => update({ [field]: value } as Partial<OverviewForm>)}
            colourName={{ value: draft.colour_name, invalidText: errors.colour_name, onChange: (value) => update({ colour_name: value }) }}
          />
        </div>
        <TextInput
          id="sku-edit-carton_count"
          labelText="Cartons"
          helperText="This many cartons ship per sellable unit."
          inputMode="numeric"
          value={draft.carton_count}
          invalid={Boolean(errors.carton_count)}
          invalidText={errors.carton_count}
          disabled={card.saving}
          onChange={(event) => update({ carton_count: event.target.value })}
        />
        <div className={styles.editWide}>
          <div className={styles.toggles}>
            <Toggle id="sku-edit-is_sellable" size="sm" labelText="Sellable" labelA="No" labelB="Yes"
              toggled={draft.is_sellable} disabled={card.saving} onToggle={(value) => update({ is_sellable: value })} />
            <Toggle id="sku-edit-do_not_reorder" size="sm" labelText="Do not reorder" labelA="Off" labelB="On"
              toggled={draft.do_not_reorder} disabled={card.saving} onToggle={(value) => update({ do_not_reorder: value })} />
            <Toggle id="sku-edit-till_no_stock_required" size="sm" labelText="No stock needed" labelA="Off" labelB="On"
              toggled={draft.till_no_stock_required} disabled={card.saving || overview.is_kit}
              onToggle={(value) => update({ till_no_stock_required: value })} />
          </div>
          <p className={styles.help}>
            Do not reorder: it still sells until stock runs out, but never appears on the reorder list.
            {" "}No stock needed: for delivery or installation charges, the till sells it without showroom stock{overview.is_kit ? " (not for kits)" : ""}.
          </p>
          {errors.till_no_stock_required && <p className={styles.fieldError}>{errors.till_no_stock_required}</p>}
          {errors.is_sellable && <p className={styles.fieldError}>{errors.is_sellable}</p>}
        </div>
      </div>
    </CardForm>
  );
}
