"use client";

import { CheckmarkFilled, Misuse, Pending } from "@carbon/icons-react";
import { FileUploaderDropContainer, FileUploaderItem, InlineNotification, Tag, Toggle } from "@carbon/react";
import { useState } from "react";
import { useCategories } from "@/components/catalogue-lists/hooks";
import { uploadSkuPhoto, type Sku } from "@/lib/api";
import type { SkuOverview } from "@/lib/catalogue-lists";
import { SKU_PHOTO_ACCEPT, pickSkuPhoto } from "@/lib/new-sku-form";
import { SHOP_HIDDEN_HELP, setSkuShopHidden } from "@/lib/shop-visibility";
import { photoCount, sectionSummary, shopReadiness } from "@/lib/sku-summary";
import { CardForm, useCardDraft } from "../edit/shared";
import { SkuThumb } from "../sku-thumb";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

function useShopSection(sku: Sku) {
  const categories = useCategories();
  const category = categories.data?.categories.find((item) => item.id === sku.category_id);
  // undefined while loading (or on error): the check reads "unknown", not "missing".
  const shopSection = !sku.category_id ? null : categories.data ? (category?.shop_category ?? null) : undefined;
  const label = categories.data?.shop_sections.find((item) => item.slug === shopSection)?.label ?? shopSection;
  return { shopSection, label };
}

function Readiness({ sku, shopSection, label }: { sku: Sku; shopSection: string | null | undefined; label: string | null | undefined }) {
  return (
    <ul className={styles.checks} aria-label="Shop readiness">
      {shopReadiness(sku, shopSection).map((check) => (
        <li key={check.key}>
          {check.ok === null ? <Pending aria-label="Checking" /> : check.ok
            ? <CheckmarkFilled className={styles.ok} aria-label="Done" />
            : <Misuse className={styles.no} aria-label="Missing" />}
          {check.label}{check.key === "shop_section" && label ? `: ${label}` : ""}
        </li>
      ))}
    </ul>
  );
}

/** Every photo slot the SKU has. The API does not say which gallery slot is a setting or detail shot. */
function Photos({ sku }: { sku: Sku }) {
  const photos = photoCount(sku);
  if (!photos) return null;
  return (
    <ul className={styles.photos} aria-label="Photos" key={sku.photo_storage_key ?? sku.updated_at}>
      {Array.from({ length: photos }, (_, index) => (
        <li key={index}>
          <SkuThumb sku={sku} slot={sku.gallery_photo_count ? index + 1 : undefined} className={styles.photo} />
          <span>{index === 0 ? "Primary" : `Photo ${index + 1}`}</span>
        </li>
      ))}
    </ul>
  );
}

function ShopEdit({ overview }: { overview: SkuOverview }) {
  const { sku } = overview;
  const card = useCardDraft(sku.id, () => ({ storefront_hidden: sku.storefront_hidden ?? false, photo: null as File | null }));
  const [photoError, setPhotoError] = useState<string | null>(null);
  const { shopSection, label } = useShopSection(sku);
  // The backend takes a first photo only; the gallery is replaced through the DasKasas catalogue import.
  const canUpload = photoCount(sku) === 0;
  const save = () => void card.save({}, async () => {
    let updated: Sku | null = null;
    if (card.draft.storefront_hidden !== (sku.storefront_hidden ?? false)) {
      updated = await setSkuShopHidden(sku.id, card.draft.storefront_hidden);
    }
    if (card.draft.photo) updated = await uploadSkuPhoto(sku.id, card.draft.photo);
    return updated;
  });
  return (
    <CardForm id="shop" saving={card.saving} failure={card.failure} onSave={save}>
      <Toggle id="sku-edit-storefront_hidden" size="sm" labelText="Hide from shop" labelA="Off" labelB="On"
        toggled={card.draft.storefront_hidden} disabled={card.saving} onToggle={(value) => card.update({ storefront_hidden: value })} />
      <p className={styles.help}>{SHOP_HIDDEN_HELP} Hidden pieces still sell in store.</p>
      <h4 className={styles.subhead}>Readiness</h4>
      <Readiness sku={sku} shopSection={shopSection} label={label} />
      <Photos sku={sku} />
      {canUpload && (
        <div className={styles.upload}>
          <span className={styles.label}>Primary photo</span>
          {card.draft.photo ? (
            <FileUploaderItem name={card.draft.photo.name} status="edit" iconDescription="Remove photo"
              onDelete={() => card.update({ photo: null })} />
          ) : (
            <FileUploaderDropContainer
              accept={SKU_PHOTO_ACCEPT}
              labelText="Drag a photo here or click to choose one"
              multiple={false}
              disabled={card.saving}
              onAddFiles={(event, { addedFiles }) => {
                const picked = pickSkuPhoto(event, addedFiles);
                setPhotoError(picked.error);
                if (picked.file) card.update({ photo: picked.file });
              }}
            />
          )}
          {photoError && <InlineNotification kind="error" lowContrast hideCloseButton title="Photo not added" subtitle={photoError} />}
          <p className={styles.help}>Uploaded when you save. Further photos come from the DasKasas catalogue import.</p>
        </div>
      )}
    </CardForm>
  );
}

export function ShopSection({ overview }: SkuSectionProps) {
  const { layout, modeOf } = useSkuSection();
  const { sku } = overview;
  const { shopSection, label } = useShopSection(sku);
  const photos = photoCount(sku);
  return (
    <SkuSectionFrame id="shop" overview={overview} summary={sectionSummary("shop", overview, { shopSection })}>
      {modeOf("shop") === "edit" ? <ShopEdit overview={overview} /> : (
        <>
          <Readiness sku={sku} shopSection={shopSection} label={label} />
          <div className={styles.tags}>
            {sku.storefront_hidden ? <Tag size="sm" type="gray">Hidden from the shop</Tag> : <Tag size="sm" type="green">Shown in the shop</Tag>}
            <span className={styles.help}>{photos === 1 ? "1 photo" : `${photos} photos`}</span>
          </div>
          {layout === "full" && <Photos sku={sku} />}
        </>
      )}
    </SkuSectionFrame>
  );
}
