"use client";

import { CheckmarkFilled, Misuse, Pending } from "@carbon/icons-react";
import { Tag } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { catalogueListKeys, listCategories } from "@/lib/catalogue-lists";
import { photoCount, sectionSummary, shopReadiness } from "@/lib/sku-summary";
import { SkuThumb } from "../sku-thumb";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

export function ShopSection({ overview }: SkuSectionProps) {
  const { layout } = useSkuSection();
  const { sku } = overview;
  const categories = useQuery({ queryKey: catalogueListKeys.categories(), queryFn: () => listCategories() });
  const category = categories.data?.categories.find((item) => item.id === sku.category_id);
  // undefined while loading (or on error): the check reads "unknown", not "missing".
  const shopSection = !sku.category_id ? null : categories.data ? (category?.shop_category ?? null) : undefined;
  const sectionLabel = categories.data?.shop_sections.find((item) => item.slug === shopSection)?.label ?? shopSection;
  const checks = shopReadiness(sku, shopSection);
  const photos = photoCount(sku);
  return (
    <SkuSectionFrame id="shop" overview={overview} summary={sectionSummary("shop", overview, { shopSection })}>
      <ul className={styles.checks} aria-label="Shop readiness">
        {checks.map((check) => (
          <li key={check.key}>
            {check.ok === null ? <Pending aria-label="Checking" /> : check.ok
              ? <CheckmarkFilled className={styles.ok} aria-label="Done" />
              : <Misuse className={styles.no} aria-label="Missing" />}
            {check.label}{check.key === "shop_section" && sectionLabel ? `: ${sectionLabel}` : ""}
          </li>
        ))}
      </ul>
      <p className={styles.tags}>
        {sku.storefront_hidden ? <Tag size="sm" type="gray">Hidden from the shop</Tag> : <Tag size="sm" type="green">Shown in the shop</Tag>}
        <span className={styles.help}>{photos === 1 ? "1 photo" : `${photos} photos`}</span>
      </p>
      {layout === "full" && photos > 0 && (
        <ul className={styles.photos} aria-label="Photos">
          {Array.from({ length: photos }, (_, index) => (
            <li key={index}>
              <SkuThumb sku={sku} slot={index + 1} className={styles.photo} />
              <span>{index === 0 ? "Primary" : `Photo ${index + 1}`}</span>
            </li>
          ))}
        </ul>
      )}
    </SkuSectionFrame>
  );
}
