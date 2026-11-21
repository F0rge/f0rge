import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PieceImage } from "@/components/piece-image";
import type { StoreProduct } from "@/lib/medusa";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";

export const countLabel = (count: number) => `${count} ${count === 1 ? "piece" : "pieces"}`;

// The mockup's category preview as a plain grid: each category with its first photo and its count.
export function CategoryTiles({ products, title, description, exclude }: { products: StoreProduct[]; title: string; description: string; exclude?: string }) {
  const tiles = SHOP_CATEGORIES.filter((category) => category.handle !== exclude).map((category) => {
    const pieces = products.filter((product) => product.categories?.some((item) => item.handle === category.handle));
    return { ...category, count: pieces.length, cover: pieces.find((product) => product.thumbnail || product.images?.length) };
  });
  return <section aria-labelledby="category-tiles-title" className="mx-auto w-full max-w-7xl p-6">
    <div className="mb-8">
      <h2 id="category-tiles-title" className="text-2xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-1 text-muted-foreground">{description}</p>
    </div>
    <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {tiles.map((tile) => <li key={tile.handle}>
        <Link href={tile.href} className="group block h-full overflow-hidden rounded-xl border bg-card transition-shadow hover:shadow-lg">
          <div className="relative aspect-[16/9] overflow-hidden bg-muted">
            <PieceImage product={tile.cover ?? { title: tile.name }} />
          </div>
          <div className="p-6">
            <h3 className="mb-2 text-xl font-semibold tracking-tight">{tile.name}</h3>
            <p className="mb-4 text-sm text-muted-foreground">{tile.blurb}</p>
            <p className="flex items-center justify-between text-sm text-muted-foreground">
              <span>{countLabel(tile.count)}</span>
              <span className="inline-flex items-center font-medium text-foreground">View all<ArrowRight aria-hidden="true" className="ml-2 size-4" /></span>
            </p>
          </div>
        </Link>
      </li>)}
    </ul>
  </section>;
}
