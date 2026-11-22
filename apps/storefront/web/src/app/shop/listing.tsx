import Link from "next/link";
import { Button } from "@f0rge/ui";
import { CategoryTiles } from "@/components/category-tiles";
import { listStoreProducts, listedPiece } from "@/lib/medusa";
import type { ShopCategory } from "@/lib/shop-categories";
import { ShopListing } from "./shop-listing";

// /shop lists every piece for sale; /shop/<handle> only the pieces the Firstout sync put in that Medusa category.
export async function Listing({ category }: { category?: ShopCategory }) {
  const products = await listStoreProducts();
  const inListing = category ? products.filter((product) => product.categories?.some((item) => item.handle === category.handle)) : products;
  const categoryId = category && inListing[0]?.categories?.find((item) => item.handle === category.handle)?.id;
  return <>
    <section aria-labelledby="listing-title" className="bg-primary">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:flex lg:items-center lg:justify-between lg:px-8 lg:py-16">
        <div className="text-3xl font-bold tracking-tight sm:text-4xl">
          <h1 id="listing-title" className="text-primary-foreground">{category?.name ?? "Shop all"}</h1>
          <p className="text-primary-foreground/80">{category?.blurb ?? "Every piece for sale."}</p>
        </div>
        <div className="mt-8 flex flex-wrap gap-3 lg:mt-0 lg:ml-4 lg:shrink-0">
          <Button size="lg" variant="secondary" nativeButton={false} role="link" render={<Link href="/#visit" />}>Visit the showroom</Button>
          <Button size="lg" variant="ghost" className="text-primary-foreground hover:bg-primary/80 hover:text-primary-foreground" nativeButton={false} role="link" render={<Link href="/help" />}>Delivery and returns</Button>
        </div>
      </div>
    </section>
    <ShopListing pieces={inListing.map(listedPiece)} categoryId={categoryId} shopAll={!category} />
    <CategoryTiles products={products} exclude={category?.handle} title={category ? "Other categories" : "Shop by category"} description="More from the showroom." />
  </>;
}
