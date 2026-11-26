"use client";

import { Catalog } from "@carbon/icons-react";
import { StaffImage } from "@/components/staff-image";
import { skuPhotoUrl, type Sku } from "@/lib/api";
import { photoCount } from "@/lib/sku-summary";
import styles from "./sku-panel.module.css";

/** Photo when the SKU has one; otherwise its swatch colour behind a catalogue icon. */
export function SkuThumb({ sku, slot, className }: {
  sku: Pick<Sku, "id" | "swatch_hex" | "gallery_photo_count" | "photo_storage_key">;
  slot?: number;
  className?: string;
}) {
  return (
    <span
      className={`${styles.thumb}${className ? ` ${className}` : ""}`}
      style={sku.swatch_hex ? { background: sku.swatch_hex } : undefined}
      aria-hidden="true"
    >
      <Catalog size={20} />
      {photoCount(sku) > 0 && <StaffImage src={skuPhotoUrl(sku.id, slot)} alt="" />}
    </span>
  );
}

/** A 16 px swatch chip, the colour name and the hex, as one inline group. */
export function ColourLine({ name, hex }: { name: string | null; hex: string | null }) {
  if (!name && !hex) return null;
  return (
    <span className={styles.colour}>
      {hex && <span className={styles.swatch} style={{ background: hex }} aria-hidden="true" />}
      {name && <span>{name}</span>}
      {hex && <code>{hex}</code>}
    </span>
  );
}
