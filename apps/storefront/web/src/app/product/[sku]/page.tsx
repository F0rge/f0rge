import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getStoreProduct } from "@/lib/medusa";
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
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { sku } = await params;
  const product = await getStoreProduct(sku);
  if (!product) notFound();
  return <ProductDetail product={product} />;
}
