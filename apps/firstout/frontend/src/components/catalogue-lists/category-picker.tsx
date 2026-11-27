"use client";

import { Link, Select, SelectItem } from "@carbon/react";

import {
  categoryOptionLabel,
  pickableCategories,
  pickableSubcategories,
  salesAccountLabel,
  subcategoryAfterCategoryChange,
  subcategoryOptionLabel,
} from "@/lib/catalogue-list-view";
import type { Category } from "@/lib/catalogue-lists";
import styles from "./catalogue-lists.module.css";

export type CategoryValue = { categoryId: string; subcategoryId: string };

export type CategoryPickerProps = {
  /** Prefix for the two select ids: `${idPrefix}-category`, `${idPrefix}-subcategory`. */
  idPrefix: string;
  /** Top-level categories from `useCategories()` (lifecycle "all"); undefined while loading. */
  categories: readonly Category[] | undefined;
  /** "" means none. */
  value: CategoryValue;
  onChange: (next: CategoryValue) => void;
  disabled?: boolean;
  readOnly?: boolean;
  /** Server or form errors for each field. */
  invalidText?: { category?: string; subcategory?: string };
  /** Shown while the list loads or when the record's category is not in it. */
  fallbackNames?: { category?: string | null; subcategory?: string | null };
  /** Hide the "Manage categories" link (e.g. inside Settings). */
  hideManageLink?: boolean;
};

/** Category then Sub-category; each category option names the sales account it posts to. */
export function CategoryPicker(props: CategoryPickerProps) {
  const { idPrefix, categories, value, onChange, disabled, readOnly, invalidText, fallbackNames } = props;
  const loading = !categories;
  const tree = categories ?? [];
  const options = pickableCategories(tree, value.categoryId);
  const subOptions = pickableSubcategories(tree, value.categoryId, value.subcategoryId);
  const selected = tree.find((category) => category.id === value.categoryId);
  const missingCategory = value.categoryId && !selected;
  const missingSub = value.subcategoryId && !subOptions.some((sub) => sub.id === value.subcategoryId);

  return (
    <div className={styles.picker}>
      <div className={styles.pair}>
        <Select
          id={`${idPrefix}-category`}
          labelText="Category"
          value={value.categoryId}
          disabled={disabled || loading}
          readOnly={readOnly}
          invalid={!!invalidText?.category}
          invalidText={invalidText?.category}
          helperText={selected ? (selected.sales_account ? `Sales post to ${salesAccountLabel(selected)}` : salesAccountLabel(selected)) : undefined}
          onChange={(event) => {
            const categoryId = event.target.value;
            onChange({ categoryId, subcategoryId: subcategoryAfterCategoryChange(tree, categoryId, value.subcategoryId) });
          }}
        >
          <SelectItem value="" text={loading ? "Loading categories…" : "No category"} />
          {missingCategory && <SelectItem value={value.categoryId} text={fallbackNames?.category ?? "Unknown category"} />}
          {options.map((category) => (
            <SelectItem
              key={category.id}
              value={category.id}
              text={categoryOptionLabel(category)}
              disabled={category.is_archived}
            />
          ))}
        </Select>
        <Select
          id={`${idPrefix}-subcategory`}
          labelText="Sub-category"
          value={value.subcategoryId}
          disabled={disabled || loading || !value.categoryId}
          readOnly={readOnly}
          invalid={!!invalidText?.subcategory}
          invalidText={invalidText?.subcategory}
          helperText={value.categoryId && !subOptions.length && !loading ? "This category has no sub-categories." : undefined}
          onChange={(event) => onChange({ categoryId: value.categoryId, subcategoryId: event.target.value })}
        >
          <SelectItem value="" text={value.categoryId ? "No sub-category" : "Choose a category first"} />
          {missingSub && <SelectItem value={value.subcategoryId} text={fallbackNames?.subcategory ?? "Unknown sub-category"} />}
          {subOptions.map((sub) => (
            <SelectItem key={sub.id} value={sub.id} text={subcategoryOptionLabel(sub)} disabled={sub.is_archived} />
          ))}
        </Select>
      </div>
      {!props.hideManageLink && (
        <Link className={styles.manage} href="/settings/categories" size="sm">Manage categories</Link>
      )}
    </div>
  );
}
