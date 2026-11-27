"use client";

import { Tag } from "@carbon/react";
import JsBarcode from "jsbarcode";
import { useEffect, useRef } from "react";
import { MATERIAL_FAMILY_LABELS, type MaterialFamily } from "@/lib/catalogue-lists";
import { categoryText, dimensionsText, formatCount, sectionSummary, skuStatusTags } from "@/lib/sku-summary";
import { ColourLine, SkuThumb } from "../sku-thumb";
import { Facts, SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import { OverviewEdit } from "../edit/overview-edit";
import styles from "../sku-panel.module.css";

type MaterialSummary = SkuSectionProps["overview"]["sku"]["other_materials"][number];

function Material({ item }: { item: MaterialSummary }) {
  return (
    <span className={styles.material}>
      {item.name}
      <Tag size="sm" type="gray">{MATERIAL_FAMILY_LABELS[item.family as MaterialFamily] ?? item.family}</Tag>
      {item.is_archived && <Tag size="sm" type="warm-gray">Archived</Tag>}
    </span>
  );
}

function Barcode({ value }: { value: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    try { JsBarcode(ref.current, value, { format: "CODE128", displayValue: false, width: 1.25, height: 38, margin: 0 }); }
    catch { ref.current.replaceChildren(); }
  }, [value]);
  return <div className={styles.barcode}><svg ref={ref} aria-hidden="true" /><code>{value || "—"}</code></div>;
}

export function OverviewSection({ overview }: SkuSectionProps) {
  const { layout, modeOf } = useSkuSection();
  const { sku } = overview;
  const full = layout === "full";
  if (modeOf("overview") === "edit") {
    return (
      <SkuSectionFrame id="overview" overview={overview} summary={sectionSummary("overview", overview)}>
        <OverviewEdit overview={overview} />
      </SkuSectionFrame>
    );
  }
  return (
    <SkuSectionFrame id="overview" overview={overview} summary={sectionSummary("overview", overview)}>
      {full && <SkuThumb sku={sku} className={styles.bigThumb} />}
      <Facts items={[
        ["Our ref", <code key="r">{sku.our_ref}</code>],
        ["Our barcode", <code key="b">{sku.our_barcode}</code>],
        ["Design", sku.design],
        ["Category", categoryText(sku), true],
        ["Colour", sku.colour_name || sku.swatch_hex ? <ColourLine name={sku.colour_name} hex={sku.swatch_hex} /> : null, true],
        ["Main material", sku.main_material ? <Material item={sku.main_material} /> : null, true],
        ["Other materials", sku.other_materials.length ? (
          <span className={styles.materials}>{sku.other_materials.map((item) => <Material key={item.id} item={item} />)}</span>
        ) : null, true],
        ["Dimensions", dimensionsText(sku), true],
        full && ["Pieces per sellable unit", sku.piece_count === null ? null : formatCount(sku.piece_count)],
        full && ["Cartons", formatCount(sku.carton_count)],
        full && ["Status", <span key="s" className={styles.tags}>{skuStatusTags(sku).map((tag) => <Tag key={tag.label} size="sm" type={tag.type}>{tag.label}</Tag>)}</span>, true],
        full && ["Internal notes", sku.notes ? <span className={styles.notes}>{sku.notes}</span> : null, true],
      ]} />
      {full && <Barcode value={sku.our_barcode} />}
    </SkuSectionFrame>
  );
}
