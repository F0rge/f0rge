import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { RotateCcw, Truck } from "lucide-react";
import { PieceImage } from "@/components/piece-image";
import { fromPrice, getStoreProduct, listStoreProducts, productPath, stockLabel, type StoreProduct } from "@/lib/medusa";
import { SHOWROOM } from "@/lib/showroom";
import { ProductDetail } from "./product-detail";

export const dynamic = "force-dynamic";

type ProductPageProps = { params: Promise<{ sku: string }> };

export async function generateMetadata({ params }: ProductPageProps): Promise<Metadata> {
  const { sku } = await params;
  const product = await getStoreProduct(sku);
  if (!product) return {};
  return {
    title: product.metadata?.seo_title || product.title,
    description: product.metadata?.seo_description || product.description || undefined,
    alternates: { canonical: productPath(product) },
  };
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
        <p className="text-sm leading-relaxed text-muted-foreground">We deliver in selected Gauteng areas. Delivery charges are shown in rand, including VAT, and confirmed in your order total before payment. Or collect from our showroom at {SHOWROOM.name}.</p>
        <Link href="/policies/delivery" className="mt-3 inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline">Delivery and collection policy</Link>
      </div>
      <div className="flex flex-col items-center text-center md:items-start md:text-left">
        <div className="mb-4 flex size-12 items-center justify-center rounded-lg bg-primary/10"><RotateCcw aria-hidden="true" className="size-6 text-primary" /></div>
        <h2 className="mb-3 text-lg font-semibold">Returns</h2>
        <p className="text-sm leading-relaxed text-muted-foreground">Changed your mind? Return a piece within 30 days of delivery or collection, unused and in the condition and packaging it arrived in. Contact us with your order number first. Bespoke pieces and pieces made to a measurement, fabric or finish chosen for your order cannot be returned for a change of mind.</p>
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
      <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {products.map((piece) => {
          const stock = stockLabel(piece);
          return <li key={piece.id}>
            <Link href={productPath(piece)} className="group block overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md">
              <div className="h-48 overflow-hidden bg-muted"><PieceImage product={piece} /></div>
              <div className="space-y-1 p-4">
                <h3 className="line-clamp-2 text-sm leading-tight font-semibold">{piece.title}</h3>
                <p className="text-xs text-muted-foreground">{[piece.categories?.[0]?.name, stock].filter(Boolean).join(" · ")}</p>
                <p className="pt-2 text-lg font-bold">{fromPrice(piece)}</p>
              </div>
            </Link>
          </li>;
        })}
      </ul>
    </div>
  </section>;
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { sku } = await params;
  const [product, catalogue] = await Promise.all([getStoreProduct(sku), listStoreProducts()]);
  if (!product) notFound();
  return <>
    <ProductDetail product={product} />
    <DeliveryAndReturns />
    <RelatedPieces products={relatedPieces(product, catalogue)} />
  </>;
}
