import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { publicPageMetadata } from "@/lib/storefront-metadata";
import { Listing } from "../listing";

export const dynamic = "force-dynamic";
type Props = { params: Promise<{ category: string }> };

const categoryFor = async (params: Props["params"]) => {
  const { category } = await params;
  return SHOP_CATEGORIES.find((item) => item.handle === category);
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const category = await categoryFor(params);
  if (!category) return {};
  const pageCopy = "pageCopy" in category ? category.pageCopy : undefined;
  return publicPageMetadata({
    title: pageCopy?.title ?? category.name,
    description: pageCopy?.description ?? `${category.blurb} Shop DasKasas furniture online or in the Bedfordview showroom.`,
    path: category.href,
    image: {
      url: `/merchandising/category-${category.handle}.webp`,
      alt: category.name,
      width: 1672,
      height: 941,
    },
  });
}

export default async function CategoryPage({ params }: Props) {
  const category = await categoryFor(params);
  if (!category) notFound();
  return <Listing category={category} />;
}
