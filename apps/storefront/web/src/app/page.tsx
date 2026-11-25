import Image from "next/image";
import Link from "next/link";
import { Clock, Mail, MapPin, Phone } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger, Badge, Button } from "@f0rge/ui";
import { StorefrontMotion } from "@/components/storefront-motion";
import { ProductCardGallery } from "@/components/product-card-gallery";
import { CategoryTiles } from "@/components/category-tiles";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
import { COLLECTION_ADDRESS, DELIVERY_DESCRIPTION } from "@/lib/checkout-fulfillment";
import { fromPrice, listStoreProducts, productPath, stockLabel, type StoreProduct } from "@/lib/medusa";
import { selectedImages } from "@/lib/product-variants";
import { POLICY_DRAFT_NOTICE, RETURNS_SUMMARY, currentCustomerPolicies } from "@/lib/customer-policies";
import { SHOWROOM } from "@/lib/showroom";

export const dynamic = "force-dynamic";

const faqs: { question: string; answer: string; returnPolicy?: true }[] = [
  {
    question: "Where is your showroom?",
    answer: `${SHOWROOM.address}. ${SHOWROOM.note} We are open ${SHOWROOM.hours.map((row) => `${row.days} ${row.time}`).join(", ")}.`,
  },
  {
    question: "Do you deliver?",
    answer: DELIVERY_DESCRIPTION,
  },
  {
    question: "Where can I collect my order?",
    answer: `Choose free collection at checkout. We’ll contact you when your order is ready to collect by appointment at ${COLLECTION_ADDRESS}.`,
  },
  {
    question: "Do I need an account to order?",
    answer: "No. You can check out as a guest.",
  },
  {
    question: "Can I return a piece?",
    answer: [RETURNS_SUMMARY.coolingOff, RETURNS_SUMMARY.changeOfMind, RETURNS_SUMMARY.howToReturn, RETURNS_SUMMARY.notReturnable].join(" "),
    returnPolicy: true,
  },
  {
    question: "What if a piece is faulty, wrong or damaged?",
    answer: "Contact us with your order number and leave the labels and packaging as they are. Your rights under the Consumer Protection Act apply. The return policy explains how faults, wrong pieces and missing parts are put right.",
    returnPolicy: true,
  },
  {
    question: "How do I contact you?",
    answer: `Call ${SHOWROOM.phones.map((phone) => phone.number).join(" or ")}, or email ${SHOWROOM.email}.`,
  },
];

function SelectedPieces({ products }: { products: StoreProduct[] }) {
  // ponytail: the first five pieces in Medusa's order; add a merchandised selection if the owner wants to choose.
  const [featured, ...others] = products.slice(0, 5);
  if (!featured) return null;
  const featuredStock = stockLabel(featured);
  return <section data-reveal id="selected-pieces" aria-labelledby="selected-pieces-title" className="mx-auto w-full max-w-7xl p-6">
    <div className="mb-6 flex items-end justify-between gap-4">
      <h2 id="selected-pieces-title" className="text-2xl font-bold tracking-tight md:text-3xl">Selected pieces</h2>
      <Link href="/shop" className="text-sm font-medium underline-offset-4 hover:underline">Shop all</Link>
    </div>
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
      <div data-product-card className="grid min-w-0 overflow-hidden rounded-xl border bg-card md:col-span-2 md:grid-cols-2">
        <ProductCardGallery title={featured.title} images={selectedImages(featured, featured.variants[0])} />
        <TrackedProductLink href={productPath(featured)} productId={featured.id} className="flex flex-col p-6 hover:underline">
          <div className="flex-1">
            <h3 className="text-2xl font-semibold">{featured.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{featuredStock}</p>
            {(featured.material || featured.categories?.[0]?.name) && <p className="mt-4 text-muted-foreground">{featured.material || featured.categories?.[0]?.name}</p>}
            <p className="mt-4 text-2xl font-bold">{fromPrice(featured)}</p>
          </div>
          <span className="mt-6 inline-flex h-9 items-center justify-center rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground sm:w-1/2">View piece</span>
        </TrackedProductLink>
      </div>
      {others.map((product) => {
        const stock = stockLabel(product);
        return <div key={product.id} data-product-card className="min-w-0 overflow-hidden rounded-xl border bg-card">
          <ProductCardGallery title={product.title} images={selectedImages(product, product.variants[0])} />
          <TrackedProductLink href={productPath(product)} productId={product.id} className="block p-4 hover:underline">
            <div className="flex items-center justify-between gap-4">
              <h3 className="min-w-0 truncate font-medium">{product.title}</h3>
              <span className="shrink-0 font-medium">{fromPrice(product)}</span>
            </div>
            {stock && <p className="mt-1 text-sm text-muted-foreground">{stock}</p>}
          </TrackedProductLink>
        </div>;
      })}
    </div>
  </section>;
}

function VisitShowroom() {
  return <section data-reveal id="visit" aria-labelledby="visit-title" className="mx-auto max-w-[1400px] px-4 py-16 md:px-6 md:py-24">
    <div className="grid gap-10 overflow-hidden rounded-xl border bg-primary p-8 text-primary-foreground md:grid-cols-2 md:p-12">
      <div className="space-y-4">
        <h2 id="visit-title" className="text-3xl font-bold tracking-tighter md:text-4xl">Visit the showroom</h2>
        <p className="md:text-lg">See the pieces in person at {SHOWROOM.name}. {SHOWROOM.note}</p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2">
        <div className="flex items-start gap-3">
          <MapPin aria-hidden="true" className="mt-0.5 size-6 shrink-0" />
          <div>
            <h3 className="mb-1 font-medium">Address</h3>
            <address className="text-sm not-italic text-primary-foreground/80">{SHOWROOM.address}</address>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <Clock aria-hidden="true" className="mt-0.5 size-6 shrink-0" />
          <div>
            <h3 className="mb-1 font-medium">Opening hours</h3>
            <table className="text-sm">
              <tbody>{SHOWROOM.hours.map((row) => <tr key={row.days}>
                <th scope="row" className="py-0.5 pr-6 text-left font-normal text-primary-foreground/80">{row.days}</th>
                <td className="py-0.5 font-medium whitespace-nowrap tabular-nums">{row.time}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <Phone aria-hidden="true" className="mt-0.5 size-6 shrink-0" />
          <div>
            <h3 className="mb-1 font-medium">Call us</h3>
            {SHOWROOM.phones.map((phone) => <p key={phone.number} className="text-sm"><span className="text-primary-foreground/80">{phone.label}: </span><span className="font-medium">{phone.number}</span></p>)}
          </div>
        </div>
        <div className="flex items-start gap-3">
          <Mail aria-hidden="true" className="mt-0.5 size-6 shrink-0" />
          <div>
            <h3 className="mb-1 font-medium">Email</h3>
            <p className="text-sm text-primary-foreground/80">For questions about a piece or an order.</p>
            <p className="mt-1 text-sm font-medium break-all">{SHOWROOM.email}</p>
          </div>
        </div>
      </div>
    </div>
  </section>;
}

export default async function HomePage() {
  const products = await listStoreProducts();

  return <StorefrontMotion>
    <section aria-labelledby="hero-title" className="relative overflow-hidden bg-background">
      <div className="mx-auto max-w-7xl lg:grid lg:grid-cols-12 lg:gap-x-8 lg:px-8">
        <div className="px-6 pt-10 pb-16 sm:pb-24 lg:col-span-7 lg:px-0 lg:pt-40 lg:pb-48 xl:col-span-6">
          <div className="mx-auto max-w-2xl lg:mx-0">
            <Badge variant="secondary" className="mb-4">Bedford Square, Bedfordview</Badge>
            <h1 id="hero-title" className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Rooms worth coming home to.</h1>
            <div className="mt-10 flex flex-wrap items-center gap-4">
              <Button size="lg" className="px-4" nativeButton={false} role="link" render={<Link href="/shop" />}>Shop all</Button>
              <Button size="lg" variant="outline" className="px-4" nativeButton={false} role="link" render={<Link href="/#visit" />}>Visit the showroom</Button>
            </div>
          </div>
        </div>
        <div className="lg:col-span-5 lg:self-center xl:col-span-6">
          <Image src="/merchandising/home-ivory-salon.webp" alt="Ivory Salon with the Avanzi sofa, Carmella armchair and Canberra coffee table" width={1672} height={941} unoptimized loading="eager" fetchPriority="high" className="aspect-video w-full object-contain" />
        </div>
      </div>
    </section>

    <SelectedPieces products={products} />
    <CategoryTiles products={products} title="Shop by category" description="Every piece in the showroom, by room." />
    <VisitShowroom />

    <section data-reveal aria-labelledby="faq-title" className="mx-auto max-w-[1400px] px-4 py-24 md:px-6 lg:py-32">
      <div className="mx-auto mb-10 max-w-2xl text-center lg:mb-14">
        <h2 id="faq-title" className="text-2xl font-bold md:text-4xl md:leading-tight">Questions</h2>
        <p className="mt-1 text-muted-foreground">About the showroom, delivery and returns.</p>
      </div>
      <Accordion className="mx-auto max-w-2xl">
        {/* Triggers inherit their font (Mantine's unlayered button reset), so the item carries it. */}
        {faqs.map((faq) => <AccordionItem key={faq.question} value={faq.question} className="text-lg font-semibold">
          <AccordionTrigger>{faq.question}</AccordionTrigger>
          <AccordionContent className="text-base font-normal text-muted-foreground">
            {faq.answer}
            {faq.returnPolicy && <> <Link href="/policies/returns">Read the return policy</Link>.{!currentCustomerPolicies() && ` ${POLICY_DRAFT_NOTICE}`}</>}
          </AccordionContent>
        </AccordionItem>)}
      </Accordion>
    </section>
  </StorefrontMotion>;
}
