"use client";

import { Button, Stepper, cn } from "@f0rge/ui";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { PieceImage } from "@/components/piece-image";
import { useProductAttention } from "@/components/analytics/use-product-attention";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";
import { zarMinorUnits } from "@/lib/analytics/money";
import { formatCustomerPrice } from "@/lib/order-money";
import { customerFacingCopy, purchaseFeedback } from "@/lib/purchase-feedback";

const assurances = [
  { title: "Delivery", description: "Selected Gauteng areas" },
  { title: "Collection", description: "Bedford Square showroom" },
  { title: "Returns", description: "Change of mind within 30 days" },
];

function formatPrice(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  return amount == null ? "Price unavailable" : formatCustomerPrice(amount, variant?.calculated_price?.currency_code);
}

function selectedImages(product: StoreProduct, variant?: MedusaVariant): string[] {
  const all = [...(variant?.images?.map((image) => image.url) || []), ...(product.images?.map((image) => image.url) || [])];
  const suitableValue = variant?.metadata?.suitable_image_urls;
  let suitable: string[] = [];
  if (Array.isArray(suitableValue)) suitable = suitableValue;
  else if (typeof suitableValue === "string") {
    try {
      const parsed: unknown = JSON.parse(suitableValue);
      if (Array.isArray(parsed)) suitable = parsed.filter((url): url is string => typeof url === "string");
    } catch { /* Invalid merchant metadata falls back to the product gallery. */ }
  }
  if (suitable?.length) return Array.from(new Set(all.filter((url) => suitable.includes(url))));
  return Array.from(new Set(all.length ? all : variant?.thumbnail ? [variant.thumbnail] : product.thumbnail ? [product.thumbnail] : []));
}

export function ProductDetail({ product }: { product: StoreProduct }) {
  const attentionRef = useProductAttention(product.id);
  const { choice, capture } = useStorefrontAnalytics();
  const first = product.variants[0];
  const [choices, setChoices] = useState<Record<string, string>>(() => Object.fromEntries((first?.options || []).map((option) => [option.option_id || option.option?.id, option.value]).filter((entry): entry is [string, string] => !!entry[0])));
  const options = (product.options || []).filter((option) => (option.values?.length || 0) > 1);
  const variant = options.length === 0 ? first : product.variants.find((candidate) => options.every((option) => candidate.options?.some((value) => (value.option_id || value.option?.id) === option.id && value.value === choices[option.id])));
  const gallery = selectedImages(product, variant);
  const [activeImage, setActiveImage] = useState<string | null>(null);
  const [requested, setRequested] = useState(1);
  const [adding, setAdding] = useState(false);
  const [bagMessage, setBagMessage] = useState("");
  const [bagFailed, setBagFailed] = useState(false);
  const feedbackRef = useRef<HTMLParagraphElement>(null);
  const image = activeImage && gallery.includes(activeImage) ? activeImage : gallery[0];
  const imagePosition = image ? gallery.indexOf(image) + 1 : 0;
  const quantity = variant?.inventory_quantity ?? 0;
  const offer = variant?.metadata?.made_to_order_offer;
  const offerObservedAt = offer?.observed_at ? Date.parse(offer.observed_at) : NaN;
  const offerFresh = Number.isFinite(offerObservedAt) && Date.now() - offerObservedAt <= 5 * 60_000 && offerObservedAt <= Date.now() + 60_000;
  const offerAvailable = !!offer && offerFresh && offer.remaining_capacity > 0 && Date.parse(offer.expires_at) > Date.now();
  const promisedWindow = offerAvailable ? (() => {
    const start = new Date();
    const end = new Date();
    start.setUTCDate(start.getUTCDate() + offer.min_lead_time_days);
    end.setUTCDate(end.getUTCDate() + offer.max_lead_time_days);
    const date = (value: Date) => new Intl.DateTimeFormat("en-ZA", { dateStyle: "medium", timeZone: "UTC" }).format(value);
    return `${date(start)} – ${date(end)}`;
  })() : null;
  const availability = !variant ? "This combination is unavailable" : quantity > 0 ? `${quantity} in stock` : offerAvailable ? `Made to order · ${offer!.min_lead_time_days}–${offer!.max_lead_time_days} days` : offer && !offerFresh ? "Made-to-order availability needs refreshing" : offer ? "Made-to-order allowance exhausted or expired" : "Currently unavailable";
  // Quantity is capped at stock, or at the made-to-order places left; the bag API takes at most 99.
  const maxQuantity = Math.min(99, quantity > 0 ? quantity : offerAvailable ? offer!.remaining_capacity : 0);
  const chosenQuantity = Math.max(1, Math.min(requested, maxQuantity));
  const canAdd = !!variant?.calculated_price && maxQuantity > 0;
  const dimensions = [variant?.length ?? product.length, variant?.width ?? product.width, variant?.height ?? product.height];
  const hasDimensions = dimensions.every((value) => value != null && value > 0);
  const material = variant?.material || product.material;
  const care = variant?.metadata?.care_instructions || product.metadata?.care_instructions;
  const description = customerFacingCopy(product.description);
  const category = product.categories?.[0]?.name;
  const feedback = bagMessage ? purchaseFeedback(bagMessage, bagFailed) : null;
  useEffect(() => { if (bagMessage) feedbackRef.current?.focus(); }, [bagMessage]);
  useEffect(() => {
    if (choice === "accepted") capture({ name: "storefront_product_viewed", properties: { product_id: product.id } });
  }, [capture, choice, product.id]);

  return <article aria-labelledby="product-title" className="relative mx-auto w-full max-w-7xl p-6">
    <div ref={attentionRef} className="product-attention-region" aria-hidden="true" />
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
      <div className="min-w-0 space-y-4">
        <div data-main-image className="relative aspect-square overflow-hidden rounded-xl bg-muted">
          {image
            ? <img key={image} src={image} alt={`${product.title}${variant?.title && variant.title !== "Default" ? `, ${variant.title}` : ""}, view ${imagePosition} of ${gallery.length}`} width={800} height={800} fetchPriority="high" className="size-full object-cover" />
            : <PieceImage product={product} />}
        </div>
        <p className="sr-only" aria-live="polite">{imagePosition ? `Image ${imagePosition} of ${gallery.length} for ${product.title}` : `No photo yet for ${product.title}`}</p>
        {gallery.length > 1 && <div role="group" aria-label="Product images" className="grid grid-cols-4 gap-4">{gallery.map((url, index) => <Button key={url} type="button" variant="ghost" aria-label={`Show image ${index + 1} of ${gallery.length}`} aria-pressed={url === image} onClick={() => {
          setActiveImage(url);
          capture({ name: "storefront_product_media_selected", properties: { product_id: product.id, media_index: index } });
        }} className={cn("aspect-square h-auto overflow-hidden rounded-xl border-2 border-transparent bg-muted p-0", url === image && "border-primary")}><img src={url} alt="" className="size-full object-cover" /></Button>)}</div>}
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
          {quantity < 1 && offerAvailable && promisedWindow && <p className="text-sm text-muted-foreground">Made to order for you: estimated ready between {promisedWindow}. {offer!.remaining_capacity} made-to-order {offer!.remaining_capacity === 1 ? "place" : "places"} currently available.</p>}
        </div>

        {(description || material || hasDimensions || care) && <div className="space-y-3 text-muted-foreground">
          {description && <p>{description}</p>}
          {(material || hasDimensions || care) && <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-sm">
            {material && <><dt className="font-medium text-foreground">Material</dt><dd>{material}</dd></>}
            {hasDimensions && <><dt className="font-medium text-foreground">Size (L × W × H)</dt><dd>{dimensions.join(" × ")} {product.metadata?.dimension_unit || ""}</dd></>}
            {care && <><dt className="font-medium text-foreground">Care</dt><dd>{care}</dd></>}
          </dl>}
        </div>}

        {options.length > 0 && <div className="space-y-4 border-t pt-6">{options.map((option) => {
          const values = option.values?.map(({ value }) => value) || Array.from(new Set(product.variants.flatMap((candidate) => candidate.options?.filter((item) => (item.option_id || item.option?.id) === option.id).map((item) => item.value) || [])));
          return <div key={option.id} className="space-y-2">
            <label htmlFor={`option-${option.id}`} className="block text-sm font-medium">{option.title}</label>
            <select id={`option-${option.id}`} value={choices[option.id] || ""} className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base md:text-sm" onChange={(event) => {
              const nextValue = event.target.value;
              const nextChoices = { ...choices, [option.id]: nextValue };
              const selected = product.variants.find((candidate) => options.every((item) => candidate.options?.some((value) => (value.option_id || value.option?.id) === item.id && value.value === nextChoices[item.id])));
              setChoices(nextChoices);
              setActiveImage(null);
              capture({ name: "storefront_product_variant_selected", properties: {
                product_id: product.id,
                option_id: option.id,
                value_index: values.indexOf(nextValue),
                ...(selected ? { variant_id: selected.id } : {}),
              } });
            }}>{values.map((value) => <option key={value} value={value}>{value}</option>)}</select>
          </div>;
        })}</div>}
        {!variant && <div className="text-sm font-medium"><Button type="button" variant="outline" onClick={() => { setChoices(Object.fromEntries((first?.options || []).map((option) => [option.option_id || option.option?.id, option.value]).filter((entry): entry is [string, string] => !!entry[0]))); setActiveImage(null); }}>Choose an available combination</Button></div>}

        <div className="space-y-6 border-t pt-6">
          {canAdd && <div className="flex justify-start"><Stepper label="Quantity" value={chosenQuantity} min={1} max={maxQuantity} onChange={setRequested} /></div>}
          {/* Mantine's unlayered button reset makes buttons inherit their font, so the wrapper carries it. */}
          <div className="text-sm font-medium">
            <Button size="lg" type="button" className="h-12 w-full" disabled={!canAdd || adding} onClick={async () => {
              if (!variant) return;
              setAdding(true); setBagMessage(""); setBagFailed(false);
              try {
                const response = await fetch("/api/bag", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ variant_id: variant.id, quantity: chosenQuantity }) });
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || "Could not add this piece");
                const valueMinor = zarMinorUnits((variant.calculated_price?.calculated_amount ?? NaN) * chosenQuantity);
                if (valueMinor !== null) capture({
                  name: "storefront_cart_item_added",
                  properties: { variant_id: variant.id, product_id: product.id, quantity: chosenQuantity, value_minor: valueMinor },
                });
                setBagFailed(false);
                setBagMessage(`Added ${chosenQuantity} × ${product.title} to your bag.`);
              } catch (error) {
                setBagFailed(true);
                setBagMessage(error instanceof Error ? error.message : "Could not add this piece");
              }
              finally { setAdding(false); }
            }}>{adding ? "Adding…" : "Add to bag"}</Button>
          </div>
          {feedback && <p ref={feedbackRef} role={feedback.role} tabIndex={feedback.tabIndex} className={cn("rounded-lg border p-4 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring", bagFailed ? "border-destructive text-destructive" : "bg-muted")}>
            {feedback.message}{!bagFailed && <> <Link href="/bag" className="font-medium underline underline-offset-4">View bag</Link></>}
          </p>}
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
