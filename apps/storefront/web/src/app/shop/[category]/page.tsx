import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { Listing } from "../listing";

export const dynamic = "force-dynamic";
type Props = { params: Promise<{ category: string }> };

const categoryFor = async (params: Props["params"]) => {
  const { category } = await params;
  return SHOP_CATEGORIES.find((item) => item.handle === category);
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const category = await categoryFor(params);
  return category ? { title: category.name, description: `${category.blurb} Shop DasKasas furniture online or in the Bedfordview showroom.`, alternates: { canonical: category.href } } : {};
}

export default async function CategoryPage({ params }: Props) {
  const category = await categoryFor(params);
  if (!category) notFound();
  return <Listing category={category} />;
}
