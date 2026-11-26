import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { RotateCcw, Truck } from "lucide-react";
import { ProductCard } from "@/components/product-card";
import { getStoreProduct, listStoreProducts, listedPiece, productPath, type StoreProduct } from "@/lib/medusa";
import { productPageCopy, productShareImage, productStructuredData } from "@/lib/product-seo";
import { POLICY_DRAFT_NOTICE, RETURNS_SUMMARY, currentCustomerPolicies } from "@/lib/customer-policies";
import { COLLECTION_ADDRESS } from "@/lib/checkout-fulfillment";
import { publicPageMetadata } from "@/lib/storefront-metadata";
import { ProductDetail } from "./product-detail";

export const dynamic = "force-dynamic";

type ProductPageProps = {
  params: Promise<{ sku: string }>;
  searchParams: Promise<{ variant?: string | string[] }>;
};

function selectedVariant(product: StoreProduct, variantId: string | string[] | undefined) {
  return product.variants.find(({ id }) => id === variantId);
}

export async function generateMetadata({ params, searchParams }: ProductPageProps): Promise<Metadata> {
  const [{ sku }, { variant }] = await Promise.all([params, searchParams]);
  const product = await getStoreProduct(sku);
  if (!product) return {};
  const selected = selectedVariant(product, variant);
  return publicPageMetadata({
    ...productPageCopy(product, selected),
    path: productPath(product),
    image: productShareImage(product, selected),
  });
}

// Same category first, then everything else, in Medusa's order (Array.sort is stable).
// ponytail: reads the whole catalogue; query Medusa by category if it grows past a few hundred pieces.
function relatedPieces(product: StoreProduct, catalogue: StoreProduct[]): StoreProduct[] {
  const categories = new Set(product.categories?.map((category) => category.handle));
  const shares = (candidate: StoreProduct) => candidate.categories?.some((category) => categories.has(category.handle)) ? 1 : 0;
  return catalogue.filter((candidate) => candidate.id !== product.id).sort((a, b) => shares(b) - shares(a)).slice(0, 4);
}

function DeliveryAndReturns() {
  return <section aria-label="Delivery and returns" className="px-4 py-8 md:py-12">
    <div className="mx-auto grid max-w-4xl gap-8 md:grid-cols-2 md:gap-12">
      <div className="flex flex-col items-center text-center md:items-start md:text-left">
        <div className="mb-4 flex size-12 items-center justify-center rounded-lg bg-primary/10"><Truck aria-hidden="true" className="size-6 text-primary" /></div>
        <h2 className="mb-3 text-lg font-semibold">Delivery or collection</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">We deliver in selected areas of Johannesburg and Pretoria. We confirm the delivery charge, including VAT, before you pay. You can also collect for free by appointment at {COLLECTION_ADDRESS}.</p>
        <Link href="/policies/delivery" className="mt-3 inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline">Delivery and collection policy</Link>
      </div>
      <div className="flex flex-col items-center text-center md:items-start md:text-left">
        <div className="mb-4 flex size-12 items-center justify-center rounded-lg bg-primary/10"><RotateCcw aria-hidden="true" className="size-6 text-primary" /></div>
        <h2 className="mb-3 text-lg font-semibold">Returns</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">{[RETURNS_SUMMARY.coolingOff, RETURNS_SUMMARY.changeOfMind, RETURNS_SUMMARY.howToReturn, RETURNS_SUMMARY.notReturnable].join(" ")}</p>
        {!currentCustomerPolicies() && <p className="mt-3 rounded-lg border p-3 text-sm" role="note">{POLICY_DRAFT_NOTICE}</p>}
        <Link href="/policies/returns" className="mt-3 inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline">Return policy</Link>
      </div>
    </div>
  </section>;
}

function RelatedPieces({ products }: { products: StoreProduct[] }) {
  if (!products.length) return null;
  return <section aria-labelledby="related-title" className="px-4 py-8 md:py-12">
    <div className="mx-auto max-w-6xl">
      <h2 id="related-title" className="mb-8 text-center text-2xl font-bold tracking-tight">More pieces</h2>
      <ul className="grid grid-cols-2 gap-x-2.5 gap-y-[22px] md:gap-x-5 md:gap-y-9 lg:grid-cols-4">
        {products.map((piece) => <ProductCard key={piece.id} piece={listedPiece(piece)} />)}
      </ul>
    </div>
  </section>;
}

async function RelatedCatalogue({ product }: { product: StoreProduct }) {
  const catalogue = await listStoreProducts().catch((error: unknown) => {
    console.error("Could not load related pieces", error);
    return [];
  });
  return <RelatedPieces products={relatedPieces(product, catalogue)} />;
}

export default async function ProductPage({ params, searchParams }: ProductPageProps) {
  const [{ sku }, { variant }] = await Promise.all([params, searchParams]);
  const product = await getStoreProduct(sku);
  if (!product) notFound();
  const variantId = selectedVariant(product, variant)?.id;
  const structuredData = productStructuredData(product, productPath(product));
  return <>
    {structuredData && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: structuredData }} />}
    <ProductDetail key={variantId ?? product.id} product={product} initialVariantId={variantId} />
    <DeliveryAndReturns />
    <Suspense fallback={null}>
      <RelatedCatalogue product={product} />
    </Suspense>
  </>;
}
