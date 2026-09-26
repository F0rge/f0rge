"use client";

import { useState } from "react";
import Link from "next/link";
import type { MedusaVariant, StoreProduct } from "@/lib/medusa";

function formatPrice(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  return amount == null ? "Price unavailable" : new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(amount);
}

function selectedImages(product: StoreProduct, variant?: MedusaVariant): string[] {
  const all = [...(variant?.images?.map((image) => image.url) || []), ...(product.images?.map((image) => image.url) || [])];
  const suitable = variant?.metadata?.suitable_image_urls;
  if (suitable?.length) return Array.from(new Set(all.filter((url) => suitable.includes(url))));
  return Array.from(new Set(all.length ? all : variant?.thumbnail ? [variant.thumbnail] : product.thumbnail ? [product.thumbnail] : []));
}

export function ProductDetail({ product }: { product: StoreProduct }) {
  const first = product.variants[0];
  const [choices, setChoices] = useState<Record<string, string>>(() => Object.fromEntries((first?.options || []).map((option) => [option.option_id || option.option?.id, option.value]).filter((entry): entry is [string, string] => !!entry[0])));
  const options = product.options || [];
  const variant = options.length === 0 ? first : product.variants.find((candidate) => options.every((option) => candidate.options?.some((value) => (value.option_id || value.option?.id) === option.id && value.value === choices[option.id])));
  const gallery = selectedImages(product, variant);
  const [activeImage, setActiveImage] = useState<string | null>(null);
  const image = activeImage && gallery.includes(activeImage) ? activeImage : gallery[0];
  const quantity = variant?.inventory_quantity ?? 0;
  const leadDays = variant?.metadata?.lead_time_days;
  const availability = !variant ? "This combination is unavailable" : quantity > 0 ? `${quantity} available` : leadDays && leadDays > 0 ? `Available to order · approx. ${leadDays} days` : "Currently unavailable";
  const dimensions = [variant?.length ?? product.length, variant?.width ?? product.width, variant?.height ?? product.height];
  const hasDimensions = dimensions.every((value) => value != null && value > 0);
  return <article className="content product-page">
    <div className="gallery">
      <div className="product-image hero-study">{image ? <img src={image} alt={`${product.title}${variant?.title ? `, ${variant.title}` : ""}`} /> : <span aria-hidden="true">Object study</span>}</div>
      {gallery.length > 1 && <div className="gallery-thumbnails" aria-label="Product images">{gallery.map((url, index) => <button key={url} type="button" className={url === image ? "active" : ""} onClick={() => setActiveImage(url)} aria-label={`Show image ${index + 1} of ${gallery.length}`} aria-pressed={url === image}><img src={url} alt="" /></button>)}</div>}
    </div>
    <div className="product-copy">
      <Link href="/" className="back-link">← All pieces</Link>
      <p className="eyebrow">The Collector / furniture</p>
      <h1>{product.title}</h1>
      <p>{product.description || "A considered addition to your living space."}</p>
      {options.length > 0 && <div className="variant-options">{options.map((option) => {
        const values = option.values?.map(({ value }) => value) || Array.from(new Set(product.variants.flatMap((candidate) => candidate.options?.filter((item) => (item.option_id || item.option?.id) === option.id).map((item) => item.value) || [])));
        return <div key={option.id}><label htmlFor={`option-${option.id}`}>{option.title}</label><select id={`option-${option.id}`} value={choices[option.id] || ""} onChange={(event) => { setChoices((current) => ({ ...current, [option.id]: event.target.value })); setActiveImage(null); }}>{values.map((value) => <option key={value} value={value}>{value}</option>)}</select></div>;
      })}</div>}
      <p className="price" aria-live="polite">{formatPrice(variant)} {variant?.calculated_price && <span>incl. VAT</span>}</p>
      <p className="sku-identity">{variant?.sku ? `SKU ${variant.sku}` : "Select an available combination"}</p>
      <p className="availability" role="status">{availability}</p>
      {(variant?.material || product.material || hasDimensions || product.metadata?.care_instructions) && <dl className="product-details">
        {(variant?.material || product.material) && <><dt>Material</dt><dd>{variant?.material || product.material}</dd></>}
        {hasDimensions && <><dt>Dimensions (L × W × H)</dt><dd>{dimensions.join(" × ")} {product.metadata?.dimension_unit || ""}</dd></>}
        {product.metadata?.care_instructions && <><dt>Care</dt><dd>{product.metadata.care_instructions}</dd></>}
      </dl>}
      <p className="preview-note">Checkout is being prepared. This is a private catalogue preview.</p>
    </div>
  </article>;
}
