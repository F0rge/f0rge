import Link from "next/link";
import { Button } from "@f0rge/ui";
import { CategoryTiles } from "@/components/category-tiles";
import { listShopProducts, listedPiece, productPath } from "@/lib/medusa";
import { AVANZI_SOFA_PATH, type ShopCategory } from "@/lib/shop-categories";
import { SHOWROOM } from "@/lib/showroom";
import { ShopListing } from "./shop-listing";

type BuyingGuide = {
  title: string;
  paragraphs: string[];
  link?: { href: string; label: string };
};

const buyingGuides: Partial<Record<ShopCategory["handle"], BuyingGuide>> = {
  "sofas-armchairs": {
    title: "Choosing a sofa for your living room",
    paragraphs: [
      "Measure the space the sofa will occupy and the route it has to take to get there. For an L-shaped sofa, check which side the return sits on when you face the sofa and whether it leaves your main walkway clear. A U-shaped layout also needs a clear opening between the two returns.",
      "If you only need one seat, measure the full width of an armchair or accent chair, including the arms. A shallower seat can make it easier to sit upright to read, while a deeper seat leaves more room to stretch out. For more seats, a straight sofa and a separate chair can be rearranged as the room changes.",
    ],
  },
  bedroom: {
    title: "Choosing bedroom furniture",
    paragraphs: [
      "Start with the bed's full footprint, including the headboard and frame. Check the mattress size separately and leave room to walk around the bed and open nearby drawers and cupboard doors. Measure the doorways, stairs and turns the piece will need to pass through as well as the space it will stand in.",
      "For a bedside table, compare its height with the top of your mattress so you can reach a lamp or a glass of water from bed. Think about what you want to keep within reach and whether a drawer or an open shelf suits you. Check dimensions and finishes on the product page before deciding.",
      "For a bedroom chair, check that you can walk between the chair and the bed and still open drawers and cupboard doors. If the chair is for a dressing table, check that the seat is a comfortable height and that the chair arms fit underneath.",
    ],
    link: { href: "/shop/sofas-armchairs", label: "Browse armchairs and accent chairs" },
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
  const guideLink = category?.handle === "sofas-armchairs" && inListing.some((product) => productPath(product) === AVANZI_SOFA_PATH)
    ? { href: AVANZI_SOFA_PATH, label: "See the Avanzi L-Shaped Sofa" }
    : guide ? guide.link : undefined;
  const heading = category && "pageCopy" in category ? category.pageCopy.heading : category?.name ?? "Shop all";
  return <>
    <section aria-labelledby="listing-title" className="bg-primary">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:flex lg:items-center lg:justify-between lg:px-8 lg:py-16">
        <div className="text-3xl font-bold tracking-tight sm:text-4xl">
          <h1 id="listing-title" className="text-primary-foreground">{heading}</h1>
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
      {guideLink && <Link href={guideLink.href} className="inline-flex min-h-11 items-center font-medium underline underline-offset-4">{guideLink.label}</Link>}
    </section>}
    <section aria-labelledby="listing-help-title" className="mx-auto w-full max-w-7xl px-4 py-8 md:px-6">
      <div className="rounded-xl border p-5 md:p-6">
        <h2 id="listing-help-title" className="text-xl font-semibold">Showroom and shopping help</h2>
        <address className="mt-2 space-y-2 text-sm not-italic">
          <p>{SHOWROOM.address}</p>
          <ul className="flex flex-wrap gap-x-5 gap-y-2">
            {SHOWROOM.phones.map(({ label, number }) => <li key={number}>{label}: <a className="font-medium underline underline-offset-4" href={`tel:${number.replace(/[^+\d]/g, "")}`}>{number}</a></li>)}
          </ul>
        </address>
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm font-medium [&_a]:underline [&_a]:underline-offset-4">
          <li><Link href="/help#contact">Showroom hours and contact</Link></li>
          <li><Link href="/policies/delivery">Delivery and collection policy</Link></li>
          <li><Link href="/policies/returns">Return policy</Link></li>
        </ul>
      </div>
    </section>
    <CategoryTiles products={products} exclude={category?.handle} title={category ? "Other categories" : "Shop by category"} description="More from the showroom." />
  </>;
}
