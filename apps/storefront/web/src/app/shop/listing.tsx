import Link from "next/link";
import { Button } from "@f0rge/ui";
import { CategoryTiles } from "@/components/category-tiles";
import { listShopProducts, listedPiece } from "@/lib/medusa";
import type { ShopCategory } from "@/lib/shop-categories";
import { ShopListing } from "./shop-listing";

const buyingGuides: Partial<Record<ShopCategory["handle"], { title: string; paragraphs: string[] }>> = {
  bedroom: {
    title: "Choosing bedroom furniture",
    paragraphs: [
      "Start with the bed's full footprint, including the headboard and frame. Check the mattress size separately and leave room to walk around the bed and open nearby drawers and cupboard doors. Measure the doorways, stairs and turns the piece will need to pass through as well as the space it will stand in.",
      "For a bedside table, compare its height with the top of your mattress so you can reach a lamp or a glass of water from bed. Think about what you want to keep within reach and whether a drawer or an open shelf suits you. Check dimensions and finishes on the product page before deciding.",
    ],
  },
  "coffee-console-tables": {
    title: "Choosing a coffee or console table",
    paragraphs: [
      "For a coffee table, start with the seating layout and measure the space between the sofa and nearby chairs. Aim for a surface close to the height of the sofa seat, within easy reach and with room to walk past. A round table can suit a space with several walking routes, while a rectangular table gives you more surface along a long sofa.",
      "For a console table, measure the wall or the back of the sofa and pay close attention to depth. In an entrance or hallway, check that the front door can swing freely and that there's a clear path past the table. Decide what needs to fit on top, such as a lamp or a tray for keys, before comparing sizes and finishes.",
    ],
  },
};

// /shop lists every piece for sale; /shop/<handle> only the pieces the Firstout sync put in that Medusa category.
export async function Listing({ category }: { category?: ShopCategory }) {
  const products = await listShopProducts();
  const inListing = category ? products.filter((product) => product.categories?.some((item) => item.handle === category.handle)) : products;
  const categoryId = category && inListing[0]?.categories?.find((item) => item.handle === category.handle)?.id;
  const guide = category && buyingGuides[category.handle];
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
    {guide && <section aria-labelledby="buying-guide" className="mx-auto w-full max-w-7xl space-y-3 px-4 py-8 md:px-6">
      <h2 id="buying-guide" className="text-xl font-semibold">{guide.title}</h2>
      {guide.paragraphs.map((paragraph) => <p key={paragraph} className="max-w-prose text-muted-foreground">{paragraph}</p>)}
    </section>}
    <CategoryTiles products={products} exclude={category?.handle} title={category ? "Other categories" : "Shop by category"} description="More from the showroom." />
  </>;
}
