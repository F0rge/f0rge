"use client";

import { Button, Stepper, cn } from "@f0rge/ui";
import { useEffect, useRef, useState } from "react";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { PieceImage } from "@/components/piece-image";
import { bagRequest, useBag } from "@/components/bag";
import { useProductAttention } from "@/components/analytics/use-product-attention";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { formatCustomerPrice } from "@/lib/order-money";
import { offerLive } from "@/lib/made-to-order";
import { pickVariant, productVariantOptions, selectedImages, variantChoices } from "@/lib/product-variants";
import { customerFacingCopy, purchaseFeedback } from "@/lib/purchase-feedback";

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
  const options = productVariantOptions(product);
  const choices = variantChoices(variant);
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
  const availability = !variant ? "This combination is unavailable" : quantity > 0 ? "In stock" : offerAvailable ? `Made to order · ${offer.min_lead_time_days}–${offer.max_lead_time_days} days` : "Out of stock";
  const skuCapacity = quantity > 0 ? quantity : offerAvailable ? offer.remaining_capacity : 0;
  const inBag = bag?.items.reduce((total, item) => total + (item.variant_id === variant?.id ? item.quantity : 0), 0) ?? 0;
  const maxQuantity = Math.max(0, skuCapacity - inBag);
  const chosenQuantity = Math.max(1, Math.min(requested, maxQuantity));
  const canAdd = !!variant?.calculated_price && maxQuantity > 0;
  const measured = variant?.metadata?.dimensions_cm;
  const dimensions = measured ? [
    { label: "Width", value: measured.width }, { label: "Depth", value: measured.depth },
    { label: "Height", value: measured.height }, { label: "Diameter", value: measured.diameter },
  ].filter(({ value }) => typeof value === "number" && value > 0) : [];
  const legacyDimensions = [variant?.length ?? product.length, variant?.width ?? product.width, variant?.height ?? product.height];
  const hasLegacyDimensions = measured == null && legacyDimensions.every((value) => value != null && value > 0);
  const pieceCount = variant?.metadata?.piece_count;
  const material = variant?.material || product.material;
  const care = variant?.metadata?.care_instructions || product.metadata?.care_instructions;
  const description = customerFacingCopy(product.description);
  const category = product.categories?.[0]?.name;
  const feedback = bagMessage ? purchaseFeedback(bagMessage, true) : null;
  useEffect(() => { if (bagMessage) feedbackRef.current?.focus(); }, [bagMessage]);
  useEffect(() => {
    if (choice === "accepted") capture({
      name: "storefront_product_viewed",
      properties: { product_id: product.id, product_title: product.title },
    });
  }, [capture, choice, product.id, product.title]);

  function selectOption(optionId: string, value: string, index: number) {
    const selected = pickVariant(product.variants, variant, optionId, value);
    if (!selected || selected.id === variant?.id) return;
    setVariantId(selected.id);
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
          {category && <p className="text-sm font-medium text-primary">{category}</p>}
          <h1 id="product-title" className="text-3xl font-bold">{product.title}</h1>
        </div>

        <div className="space-y-2">
          <p id="product-price" aria-live="polite" className="text-3xl font-bold">{formatPrice(variant)}</p>
          <p className="text-sm text-muted-foreground">
            {variant?.calculated_price && <>incl. VAT · </>}
            <span id="product-sku">{variant?.sku ? `SKU ${variant.sku}` : "Select an available combination"}</span>
            {" · "}<span role="status">{availability}</span>
          </p>
          {quantity < 1 && offerAvailable && promisedWindow && <p className="text-sm text-muted-foreground">Made to order for you. Estimated ready between {promisedWindow}.</p>}
        </div>

        {(description || material || dimensions.length > 0 || hasLegacyDimensions || pieceCount || care) && <div className="space-y-3 text-muted-foreground">
          {description && <p>{description}</p>}
          {(material || dimensions.length > 0 || hasLegacyDimensions || pieceCount || care) && <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
            {material && <><dt className="font-medium text-foreground">Material</dt><dd>{material}</dd></>}
            {dimensions.map(({ label, value }) => <div className="contents" key={label}><dt className="font-medium text-foreground">{label}</dt><dd>{value} cm</dd></div>)}
            {hasLegacyDimensions && <><dt className="font-medium text-foreground">Size (L × W × H)</dt><dd>{legacyDimensions.join(" × ")} {product.metadata?.dimension_unit || ""}</dd></>}
            {pieceCount != null && pieceCount > 0 && <><dt className="font-medium text-foreground">Pieces included</dt><dd>{pieceCount}</dd></>}
            {care && <><dt className="font-medium text-foreground">Care</dt><dd>{care}</dd></>}
          </dl>}
        </div>}

        {options.length > 0 && <div className="space-y-4 border-t pt-6">
          {options.map(({ id, title, availableValues }) => (
            <fieldset key={id} className="min-w-0 space-y-2">
              <legend className="text-sm font-medium">{title}</legend>
              <div className="flex flex-wrap gap-2">
                {availableValues.map((value, index) => (
                  <Button
                    key={value}
                    type="button"
                    variant={choices[id] === value ? "default" : "outline"}
                    className="h-auto min-h-11 max-w-full whitespace-normal text-start"
                    aria-pressed={choices[id] === value}
                    onClick={() => selectOption(id, value, index)}
                  >
                    {value}
                  </Button>
                ))}
              </div>
            </fieldset>
          ))}
        </div>}

        <div className="space-y-6 border-t pt-6">
          {skuCapacity > 0 && maxQuantity === 0 && <p className="text-sm text-muted-foreground">You have the available quantity of this option in your bag.</p>}
          {canAdd && <div className="flex justify-start"><Stepper label="Quantity" value={chosenQuantity} min={1} max={maxQuantity} onChange={setRequested} /></div>}
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
