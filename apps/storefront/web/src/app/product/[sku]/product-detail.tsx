"use client";

import { Button, Stepper, cn } from "@f0rge/ui";
import Link from "next/link";
import { Fragment, useEffect, useRef, useState } from "react";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { PieceImage } from "@/components/piece-image";
import { bagRequest, useBag } from "@/components/bag";
import { useProductAttention } from "@/components/analytics/use-product-attention";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { formatCustomerPrice } from "@/lib/order-money";
import { offerLive } from "@/lib/made-to-order";
import { publishedDimensions, unqualifiedLegacySize } from "@/lib/product-dimensions";
import { selectedImages } from "@/lib/product-variants";
import { customerFacingCopy, purchaseFeedback } from "@/lib/purchase-feedback";
import { addableRange, batchPriceParts, coversMinimum, sellRules } from "@/lib/sell-rules";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { DimensionsFit } from "./dimensions-fit";
import { VariantSelector } from "./variant-selector";

const assurances = [
  { title: "Delivery", description: "Selected areas in Johannesburg and Pretoria" },
  { title: "Collection", description: "Free by appointment in Wynberg" },
  { title: "Returns", description: "Change of mind within 30 days" },
];

function formatPrice(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  return amount == null ? "Price unavailable" : formatCustomerPrice(amount, variant?.calculated_price?.currency_code);
}

export function ProductDetail({ product, initialVariantId }: { product: StoreProduct; initialVariantId?: string }) {
  const attentionRef = useProductAttention(product.id);
  const { choice, capture } = useStorefrontAnalytics();
  const [variantId, setVariantId] = useState(initialVariantId ?? product.variants[0]?.id);
  const variant = product.variants.find((candidate) => candidate.id === variantId) ?? product.variants[0];
  const gallery = selectedImages(product, variant);
  const [activeAngle, setActiveAngle] = useState(0);
  const [requested, setRequested] = useState(1);
  const [adding, setAdding] = useState(false);
  const [bagMessage, setBagMessage] = useState("");
  const { bag, setBag, setOpen: openBag } = useBag();
  const feedbackRef = useRef<HTMLParagraphElement>(null);
  const image = gallery[activeAngle] ?? gallery[0];
  const imagePosition = image ? gallery.indexOf(image) + 1 : 0;
  const quantity = variant?.inventory_quantity ?? 0;
  const offer = variant?.metadata?.made_to_order_offer;
  const offerAvailable = offerLive(offer);
  const promisedWindow = offerAvailable ? (() => {
    const start = new Date();
    const end = new Date();
    start.setUTCDate(start.getUTCDate() + offer.min_lead_time_days);
    end.setUTCDate(end.getUTCDate() + offer.max_lead_time_days);
    const date = (value: Date) => new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeZone: "UTC" }).format(value);
    return `${date(start)} – ${date(end)}`;
  })() : null;
  const skuCapacity = quantity > 0 ? quantity : offerAvailable ? offer.remaining_capacity : 0;
  // Sold in multiples: the bag total for this variant stays a multiple, at least the minimum.
  const rules = sellRules(variant?.metadata);
  const orderable = coversMinimum(rules, skuCapacity);
  const availability = !variant ? "This combination is unavailable"
    : skuCapacity > 0 && !orderable ? "Not available to order"
      : quantity > 0 ? "In stock" : offerAvailable ? `Made to order · ${offer.min_lead_time_days}–${offer.max_lead_time_days} days` : "Out of stock";
  const inBag = bag?.items.reduce((total, item) => total + (item.variant_id === variant?.id ? item.quantity : 0), 0) ?? 0;
  const { least: leastToAdd, most: maxQuantity } = addableRange(rules, skuCapacity, inBag);
  const chosenQuantity = Math.max(leastToAdd, Math.min(requested, maxQuantity));
  const canAdd = !!variant?.calculated_price && maxQuantity >= leastToAdd;
  const batch = variant?.calculated_price ? batchPriceParts(variant.calculated_price.calculated_amount, variant.calculated_price.currency_code, rules) : null;
  const measurements = publishedDimensions(product, variant);
  const legacySize = unqualifiedLegacySize(product, variant);
  const material = variant?.material || product.material;
  const care = variant?.metadata?.care_instructions || product.metadata?.care_instructions;
  const description = customerFacingCopy(product.description);
  const category = product.categories?.[0];
  const collection = SHOP_CATEGORIES.find(({ handle }) => product.categories?.some((item) => item.handle === handle));
  const feedback = bagMessage ? purchaseFeedback(bagMessage, true) : null;
  useEffect(() => { if (bagMessage) feedbackRef.current?.focus(); }, [bagMessage]);
  useEffect(() => {
    if (choice === "accepted") capture({
      name: "storefront_product_viewed",
      properties: { product_id: product.id, product_title: product.title },
    });
  }, [capture, choice, product.id, product.title]);

  function selectOption(optionId: string, index: number, selected: MedusaVariant) {
    if (selected.id === variant?.id) return;
    setVariantId(selected.id);
    setActiveAngle(0);
    setRequested(1);
    setBagMessage("");
    capture({
      name: "storefront_product_variant_selected",
      properties: { product_id: product.id, option_id: optionId, value_index: index, variant_id: selected.id },
    });
  }

  return <article aria-labelledby="product-title" className="relative mx-auto w-full max-w-7xl p-6">
    <div ref={attentionRef} className="product-attention-region" aria-hidden="true" />
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
      <div className="min-w-0 space-y-4">
        <div data-main-image className="relative aspect-square overflow-hidden rounded-xl bg-muted">
          {image
            ? <img key={image} src={image} alt={`${product.title}${variant?.title && variant.title !== "Default" ? `, ${variant.title}` : ""}, view ${imagePosition} of ${gallery.length}`} width={800} height={800} fetchPriority="high" className="size-full object-contain" />
            : <PieceImage product={{ title: product.title }} />}
        </div>
        <p className="sr-only" aria-live="polite">{imagePosition ? `Image ${imagePosition} of ${gallery.length} for ${product.title}` : `No photo yet for ${product.title}`}</p>
        {gallery.length > 1 && <div role="group" aria-label="Product images" className="grid grid-cols-4 gap-4">{gallery.map((url, index) => <Button key={url} type="button" variant="ghost" aria-label={`Show image ${index + 1} of ${gallery.length}`} aria-pressed={url === image} onClick={() => {
          setActiveAngle(index);
          capture({ name: "storefront_product_media_selected", properties: { product_id: product.id, media_index: index } });
        }} className={cn("aspect-square h-auto overflow-hidden rounded-xl border-2 border-transparent bg-muted p-0", url === image && "border-primary")}>
          <img src={url} alt="" width={160} height={160} loading="lazy" fetchPriority="low" decoding="async" className="size-full object-contain" />
        </Button>)}</div>}
      </div>

      <div className="min-w-0 space-y-8 self-start lg:sticky lg:top-20">
        <div className="space-y-1">
          {category && <p className="text-sm font-medium text-primary">
            {collection
              ? <Link href={collection.href} className="underline underline-offset-4">{collection.name}</Link>
              : category.name}
          </p>}
          <h1 id="product-title" className="text-3xl font-bold">{product.title}</h1>
        </div>

        <div className="space-y-2">
          <p id="product-price" aria-live="polite" className="text-3xl font-bold">{formatPrice(variant)}</p>
          {/* Each part stays whole; the line may wrap only between parts. */}
          {batch && <p id="product-batch" className="text-sm text-muted-foreground">{batch.map((part, index) => <Fragment key={part}>
            <span className="whitespace-nowrap">{part}{index < batch.length - 1 && " ·"}</span>{index < batch.length - 1 && " "}
          </Fragment>)}</p>}
          <p className="text-sm text-muted-foreground">
            {variant?.calculated_price && <>incl. VAT · </>}
            <span id="product-sku">{variant?.sku ? `SKU ${variant.sku}` : "Select an available combination"}</span>
            {" · "}<span role="status">{availability}</span>
          </p>
          {quantity < 1 && offerAvailable && promisedWindow && <p className="text-sm text-muted-foreground">Made to order for you. Estimated ready between {promisedWindow}.</p>}
        </div>

        {(description || material || legacySize || care) && <div className="space-y-3 text-muted-foreground">
          {description && <p>{description}</p>}
          {(material || legacySize || care) && <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
            {material && <><dt className="font-medium text-foreground">Material</dt><dd>{material}</dd></>}
            {legacySize && <><dt className="font-medium text-foreground">Size (L × W × H)</dt><dd>{legacySize}</dd></>}
            {care && <><dt className="font-medium text-foreground">Care</dt><dd>{care}</dd></>}
          </dl>}
        </div>}

        <VariantSelector product={product} active={variant} onSelect={selectOption} />

        <DimensionsFit title={product.title} sku={variant?.sku} gallery={gallery} measurements={measurements} />

        <div className="space-y-6 border-t pt-6">
          {skuCapacity > 0 && maxQuantity < leastToAdd && <p className="text-sm text-muted-foreground">{inBag > 0
            ? "You have the available quantity of this option in your bag."
            : `Only ${skuCapacity} available, fewer than the minimum order of ${leastToAdd}.`}</p>}
          {canAdd && <div className="flex justify-start"><Stepper label="Quantity" value={chosenQuantity} min={leastToAdd} max={maxQuantity} step={rules.multiple} onChange={setRequested} /></div>}
          {/* Mantine's unlayered button reset makes buttons inherit their font, so the wrapper carries it. */}
          <div className="text-sm font-medium">
            <Button size="lg" type="button" className="h-12 w-full" disabled={!canAdd || adding} onClick={async () => {
              if (!variant) return;
              setAdding(true); setBagMessage("");
              try {
                setBag(await bagRequest("POST", "/api/bag", { variant_id: variant.id, quantity: chosenQuantity }));
                setRequested(1);
                const valueMinor = zarMinorUnits((variant.calculated_price?.calculated_amount ?? NaN) * chosenQuantity);
                if (valueMinor !== null) capture({
                  name: "storefront_cart_item_added",
                  properties: {
                    variant_id: variant.id,
                    product_id: product.id,
                    product_title: product.title,
                    quantity: chosenQuantity,
                    value_minor: valueMinor,
                  },
                });
                openBag(true);
              } catch (error) {
                setBagMessage(error instanceof Error ? error.message : "Could not add this piece");
              }
              finally { setAdding(false); }
            }}>{adding ? "Adding…" : "Add to bag"}</Button>
          </div>
          {feedback && <p ref={feedbackRef} role={feedback.role} tabIndex={feedback.tabIndex} className="rounded-lg border border-destructive p-4 text-sm text-destructive outline-none focus-visible:ring-2 focus-visible:ring-ring">{feedback.message}</p>}
        </div>

        <div className="border-t pt-6">
          <ul className="grid grid-cols-3 gap-4 text-center text-sm">{assurances.map((item) => <li key={item.title} className="space-y-1">
            <span className="block font-medium">{item.title}</span>
            <span className="block text-muted-foreground">{item.description}</span>
          </li>)}</ul>
        </div>
      </div>
    </div>
  </article>;
}
