import type { ComponentType } from "react";
import type { SkuSectionId } from "@/lib/sku-summary";
import { ActivitySection } from "./activity";
import { KitSection } from "./kit";
import { OverviewSection } from "./overview";
import { PricingSection } from "./pricing";
import { ShopSection } from "./shop";
import { StockSection } from "./stock";
import { SupplySection } from "./supply";
import type { SkuSectionProps } from "./section";

/** The seven sections, in the one order both the panel and the full view use. */
export const SKU_SECTIONS: readonly { id: SkuSectionId; Component: ComponentType<SkuSectionProps> }[] = [
  { id: "overview", Component: OverviewSection },
  { id: "stock", Component: StockSection },
  { id: "pricing", Component: PricingSection },
  { id: "supply", Component: SupplySection },
  { id: "shop", Component: ShopSection },
  { id: "kit", Component: KitSection },
  { id: "activity", Component: ActivitySection },
];

export { SkuSectionFrame, SkuSectionStateContext, useSkuSection, Facts } from "./section";
export type { SkuCardEditing, SkuSectionLayout, SkuSectionMode, SkuSectionProps, SkuSectionState } from "./section";
