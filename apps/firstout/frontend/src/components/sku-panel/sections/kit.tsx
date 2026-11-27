"use client";

import { InlineNotification, SkeletonText } from "@carbon/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { SkuBomEditor } from "@/components/sku-bom-editor";
import { listSkuBom } from "@/lib/api";
import type { SkuOverview } from "@/lib/catalogue-lists";
import { referenceQueries } from "@/lib/queries";
import { formatCount, sectionSummary } from "@/lib/sku-summary";
import { SkuLink } from "@/components/sku-link";
import { CardForm, refreshSku } from "../edit/shared";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

function KitRecipe({ skuId }: { skuId: string }) {
  const bom = useQuery({ queryKey: ["sku-bom", skuId], queryFn: () => listSkuBom(skuId) });
  // BOM lines carry ids only; the shared SKU reference list names them.
  const skus = useQuery(referenceQueries.skus);
  if (bom.isPending) return <SkeletonText paragraph lineCount={2} />;
  if (bom.error) return <InlineNotification kind="error" lowContrast hideCloseButton title="Recipe unavailable" subtitle={bom.error.message} />;
  const byId = new Map((skus.data ?? []).map((item) => [item.id, item]));
  const ids = bom.data.map((line) => line.component_sku_id);
  return (
    <ul className={styles.lines} aria-label="Components">
      {bom.data.map((line) => {
        const part = byId.get(line.component_sku_id);
        return (
          <li key={line.id}>
            <span>
              <SkuLink id={line.component_sku_id} context={{ ids, label: "Kit parts" }}>{part?.our_ref ?? "Component"}</SkuLink>
              {part && <small>{part.name}</small>}
            </span>
            <span>× {formatCount(line.qty)}</span>
          </li>
        );
      })}
    </ul>
  );
}

/** The existing recipe editor, saved from the card's foot. */
function KitEdit({ overview }: { overview: SkuOverview }) {
  const { editing } = useSkuSection();
  const client = useQueryClient();
  const skus = useQuery(referenceQueries.skus);
  const control = useRef<{ save: () => Promise<void> } | null>(null);
  const [saving, setSaving] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const report = editing?.setDirty;
  return (
    <CardForm id="kit" saving={saving} failure={failure} onSave={async () => {
      if (!dirty) { editing?.finish(); return; }
      setSaving(true);
      setFailure(null);
      await control.current?.save();
      setSaving(false);
    }}>
      {!overview.is_kit && <p className={styles.help}>Add components to sell this SKU as a set built from other SKUs.</p>}
      <SkuBomEditor
        sku={overview.sku}
        skus={skus.data ?? []}
        open
        variant="section"
        canMutate
        control={control}
        onDirtyChange={(next) => { setDirty(next); report?.(next); }}
        onClose={() => undefined}
        onSaved={async () => {
          await refreshSku(client, overview.sku.id);
          report?.(false);
          editing?.finish();
        }}
        onError={setFailure}
      />
    </CardForm>
  );
}

export function KitSection({ overview }: SkuSectionProps) {
  const { modeOf } = useSkuSection();
  const uses = overview.used_in_kits;
  return (
    <SkuSectionFrame id="kit" overview={overview} summary={sectionSummary("kit", overview)}>
      {modeOf("kit") === "edit" ? <KitEdit overview={overview} />
        : overview.is_kit ? <KitRecipe skuId={overview.sku.id} /> : <p className={styles.help}>Not a kit.</p>}
      {uses.length > 0 && (
        <>
          <h4 className={styles.subhead}>Used in</h4>
          <ul className={styles.lines}>
            {uses.map((use) => (
              <li key={use.parent_sku_id}>
                <span>
                  <SkuLink id={use.parent_sku_id} context={{ ids: uses.map((item) => item.parent_sku_id), label: "Kits" }}>{use.our_ref}</SkuLink>
                  <small>{use.name}{use.parent_is_archived ? " · archived" : ""}</small>
                </span>
                <span>× {formatCount(use.qty)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </SkuSectionFrame>
  );
}
