"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";
import { useProductAttention } from "@/components/analytics/use-product-attention";
import { useStorefrontAnalytics } from "@/components/analytics/analytics-provider";

function formatPrice(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  return amount == null ? "Price unavailable" : new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(amount);
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
  const [adding, setAdding] = useState(false);
  const [bagMessage, setBagMessage] = useState("");
  const image = activeImage && gallery.includes(activeImage) ? activeImage : gallery[0];
  const imagePosition = image ? gallery.indexOf(image) + 1 : 0;
  const quantity = variant?.inventory_quantity ?? 0;
  const leadDays = Number(variant?.metadata?.lead_time_days || 0);
  const availability = !variant ? "This combination is unavailable" : quantity > 0 ? `${quantity} available` : leadDays && leadDays > 0 ? `Available to order · approx. ${leadDays} days` : "Currently unavailable";
  const dimensions = [variant?.length ?? product.length, variant?.width ?? product.width, variant?.height ?? product.height];
  const hasDimensions = dimensions.every((value) => value != null && value > 0);
  const care = variant?.metadata?.care_instructions || product.metadata?.care_instructions;
  useEffect(() => {
    if (choice === "accepted") capture({ name: "storefront_product_viewed", properties: { product_id: product.id } });
  }, [capture, choice, product.id]);

  return <article className="content product-page">
    <div className="gallery">
      <div ref={attentionRef} className="product-image hero-study">{image ? <img src={image} alt={`${product.title}${variant?.title ? `, ${variant.title}` : ""}, view ${imagePosition} of ${gallery.length}`} /> : <span aria-hidden="true">Object study</span>}</div>
      <p className="sr-only" aria-live="polite">{imagePosition ? `Image ${imagePosition} of ${gallery.length} for ${product.title}` : `No image for ${product.title}`}</p>
      {gallery.length > 1 && <div className="gallery-thumbnails" aria-label="Product images">{gallery.map((url, index) => <button key={url} type="button" className={url === image ? "active" : ""} onClick={() => {
        setActiveImage(url);
        capture({ name: "storefront_product_media_selected", properties: { product_id: product.id, media_index: index } });
      }} aria-label={`Show image ${index + 1} of ${gallery.length}`} aria-pressed={url === image}><img src={url} alt="" /></button>)}</div>}
    </div>
    <div className="product-copy">
      <Link href="/shop" className="back-link">← All pieces</Link>
      <p className="eyebrow">The Collector / furniture</p>
      <h1>{product.title}</h1>
      <p>{product.description || "A considered addition to your living space."}</p>
      {options.length > 0 && <div className="variant-options">{options.map((option) => {
        const values = option.values?.map(({ value }) => value) || Array.from(new Set(product.variants.flatMap((candidate) => candidate.options?.filter((item) => (item.option_id || item.option?.id) === option.id).map((item) => item.value) || [])));
        return <div key={option.id}><label htmlFor={`option-${option.id}`}>{option.title}</label><select id={`option-${option.id}`} value={choices[option.id] || ""} onChange={(event) => {
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
        }}>{values.map((value) => <option key={value} value={value}>{value}</option>)}</select></div>;
      })}</div>}
      {!variant && <button type="button" className="reset-variant" onClick={() => { setChoices(Object.fromEntries((first?.options || []).map((option) => [option.option_id || option.option?.id, option.value]).filter((entry): entry is [string, string] => !!entry[0]))); setActiveImage(null); }}>Choose an available combination</button>}
      <p className="price" aria-live="polite">{formatPrice(variant)} {variant?.calculated_price && <span>incl. VAT</span>}</p>
      <p className="sku-identity">{variant?.sku ? `SKU ${variant.sku}` : "Select an available combination"}</p>
      <p className="availability" role="status">{availability}</p>
      {(variant?.material || product.material || hasDimensions || care) && <dl className="product-details">
        {(variant?.material || product.material) && <><dt>Material</dt><dd>{variant?.material || product.material}</dd></>}
        {hasDimensions && <><dt>Dimensions (L × W × H)</dt><dd>{dimensions.join(" × ")} {product.metadata?.dimension_unit || ""}</dd></>}
        {care && <><dt>Care</dt><dd>{care}</dd></>}
      </dl>}
      <button className="add-to-bag" type="button" disabled={!variant || !variant.calculated_price || quantity < 1 || adding} onClick={async () => {
        if (!variant) return;
        setAdding(true); setBagMessage("");
        try {
          const response = await fetch("/api/bag", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ variant_id: variant.id, quantity: 1 }) });
          const result = await response.json();
          if (!response.ok) throw new Error(result.message || "Could not add this piece");
          setBagMessage("Added to bag. Review your bag when ready.");
        } catch (error) { setBagMessage(error instanceof Error ? error.message : "Could not add this piece"); }
        finally { setAdding(false); }
      }}>{adding ? "Adding…" : "Add to bag"}</button>
      {bagMessage && <p role="status" className="bag-feedback">{bagMessage} <Link href="/bag">View bag</Link></p>}
    </div>
  </article>;
}
