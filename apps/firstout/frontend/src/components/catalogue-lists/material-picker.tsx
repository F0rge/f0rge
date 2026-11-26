"use client";

import { DismissibleTag, Link, Select, SelectItem, SelectItemGroup, Tag } from "@carbon/react";

import { addableMaterials, groupMaterials } from "@/lib/catalogue-list-view";
import { MATERIAL_FAMILY_LABELS, type Material } from "@/lib/catalogue-lists";
import styles from "./catalogue-lists.module.css";

export type MaterialValue = { mainId: string; otherIds: string[] };

export type MaterialPickerProps = {
  /** Prefix for ids: `${idPrefix}-main-material`, `${idPrefix}-add-material`. */
  idPrefix: string;
  /** Materials from `useMaterials()` (lifecycle "all"); undefined while loading. */
  materials: readonly Material[] | undefined;
  /** mainId "" means none; otherIds in display order. */
  value: MaterialValue;
  onChange: (next: MaterialValue) => void;
  disabled?: boolean;
  readOnly?: boolean;
  invalidText?: { main?: string; others?: string };
  /** Names for ids the list does not hold (e.g. while loading), from the SKU response. */
  fallbackNames?: Record<string, string>;
  hideManageLink?: boolean;
};

/** Main material (grouped by family) and Other materials as removable tags. */
export function MaterialPicker(props: MaterialPickerProps) {
  const { idPrefix, materials, value, onChange, disabled, readOnly, invalidText, fallbackNames } = props;
  const loading = !materials;
  const list = materials ?? [];
  const byId = new Map(list.map((material) => [material.id, material]));
  const name = (id: string) => byId.get(id)?.name ?? fallbackNames?.[id] ?? "Unknown material";
  const groups = groupMaterials(list, [value.mainId]);
  const mainKnown = !value.mainId || groups.some((group) => group.materials.some((m) => m.id === value.mainId));
  const addable = addableMaterials(list, value.mainId, value.otherIds);
  const locked = disabled || readOnly;

  return (
    <div className={styles.picker}>
      <Select
        id={`${idPrefix}-main-material`}
        labelText="Main material"
        value={value.mainId}
        disabled={disabled || loading}
        readOnly={readOnly}
        invalid={!!invalidText?.main}
        invalidText={invalidText?.main}
        onChange={(event) => {
          const mainId = event.target.value;
          onChange({ mainId, otherIds: value.otherIds.filter((id) => id !== mainId) });
        }}
      >
        <SelectItem value="" text={loading ? "Loading materials…" : "No main material"} />
        {!mainKnown && <SelectItem value={value.mainId} text={name(value.mainId)} />}
        {groups.map((group) => (
          <SelectItemGroup key={group.family} label={group.label}>
            {group.materials.map((material) => (
              <SelectItem
                key={material.id}
                value={material.id}
                text={material.is_archived ? `${material.name} · archived` : material.name}
                disabled={material.is_archived}
              />
            ))}
          </SelectItemGroup>
        ))}
      </Select>
      <fieldset className={styles.others} aria-describedby={invalidText?.others ? `${idPrefix}-others-error` : undefined}>
        <legend className="cds--label">Other materials</legend>
        <div className={styles.tags}>
          {value.otherIds.length === 0 && <span className="cds--type-helper-text-01">None</span>}
          {value.otherIds.map((id) => {
            const material = byId.get(id);
            const text = material?.is_archived ? `${name(id)} · archived` : name(id);
            return locked ? (
              <Tag key={id} type="gray" size="md">{text}</Tag>
            ) : (
              <DismissibleTag
                key={id}
                type="gray"
                text={text}
                title={`Remove ${name(id)}`}
                onClose={() => onChange({ mainId: value.mainId, otherIds: value.otherIds.filter((other) => other !== id) })}
              />
            );
          })}
        </div>
        {!locked && (
          <Select
            id={`${idPrefix}-add-material`}
            labelText="Add material"
            hideLabel
            size="sm"
            value=""
            disabled={loading || !addable.length}
            onChange={(event) => {
              if (event.target.value) onChange({ mainId: value.mainId, otherIds: [...value.otherIds, event.target.value] });
            }}
          >
            <SelectItem value="" text={addable.length ? "Add material…" : "No more materials to add"} />
            {groupMaterials(addable).map((group) => (
              <SelectItemGroup key={group.family} label={MATERIAL_FAMILY_LABELS[group.family]}>
                {group.materials.map((material) => (
                  <SelectItem key={material.id} value={material.id} text={material.name} />
                ))}
              </SelectItemGroup>
            ))}
          </Select>
        )}
        {invalidText?.others && (
          <p id={`${idPrefix}-others-error`} className={`cds--form-requirement ${styles.error}`}>{invalidText.others}</p>
        )}
      </fieldset>
      {!props.hideManageLink && (
        <Link className={styles.manage} href="/settings/materials" size="sm">Manage materials</Link>
      )}
    </div>
  );
}
