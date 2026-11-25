import type { Metadata } from "next";
import Link from "next/link";
import { Ban, CalendarClock, Clock, Mail, MapPin, PackageX, Phone, Receipt, RefreshCw, Store, Truck, Undo2, type LucideIcon } from "lucide-react";
import { COLLECTION_ADDRESS, COLLECTION_INSTRUCTIONS, DELIVERY_DESCRIPTION } from "@/lib/checkout-fulfillment";
import { POLICY_DRAFT_NOTICE, RETURNS_SUMMARY, currentCustomerPolicies } from "@/lib/customer-policies";
import { SHOWROOM } from "@/lib/showroom";

// Rendered per request so the layout's robots meta reads the live indexing switch.
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Help",
  description: "Delivery, collection, returns and how to reach the DasKasas showroom.",
  alternates: { canonical: "/help" },
};

// Every line restates the delivery, return and refund policies or the showroom facts; the policies stay the full text.
const columns: { id: string; title: string; items: { icon: LucideIcon; title: string; description: string }[] }[] = [
  {
    id: "delivery",
    title: "Delivery and collection",
    items: [
      { icon: Truck, title: "Delivery", description: DELIVERY_DESCRIPTION },
      { icon: Receipt, title: "Delivery charges", description: "Shown in rand, including VAT, and confirmed in your order total before payment." },
      { icon: Store, title: "Collection", description: `${COLLECTION_ADDRESS}. ${COLLECTION_INSTRUCTIONS}` },
      { icon: Clock, title: "Showroom hours", description: `${SHOWROOM.hours.map((row) => `${row.days} ${row.time}`).join(", ")}.` },
    ],
  },
  {
    id: "returns",
    title: "Returns",
    items: [
      { icon: CalendarClock, title: "Online orders: 7 days to cancel", description: RETURNS_SUMMARY.coolingOff },
      { icon: RefreshCw, title: "Change of mind", description: RETURNS_SUMMARY.changeOfMind },
      { icon: Undo2, title: "How to return", description: `${RETURNS_SUMMARY.howToReturn} ${RETURNS_SUMMARY.changeOfMindCosts}` },
      { icon: Ban, title: "Not returnable for a change of mind", description: RETURNS_SUMMARY.notReturnable },
      { icon: PackageX, title: "Wrong, faulty or not as described", description: "Leave the labels and packaging as they are and tell us straight away. A wrong piece, missing parts or a piece that does not match its description is collected at no charge, and the piece and its delivery charge are refunded. Your rights under the Consumer Protection Act apply to faults." },
    ],
  },
];

const policies = [
  { label: "Delivery and collection", href: "/policies/delivery" },
  { label: "Return policy", href: "/policies/returns" },
  { label: "Refund policy", href: "/policies/refunds" },
  { label: "Terms and conditions", href: "/policies/terms" },
  { label: "Privacy policy", href: "/policies/privacy" },
];

export default function HelpPage() {
  return <div className="mx-auto w-full max-w-7xl px-4 py-10 md:px-6 md:py-16">
    <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Help</h1>
    <p className="mt-2 text-muted-foreground">Delivery, collection and returns, and how to reach us.</p>

    <div className="mt-10 grid grid-cols-1 gap-12 md:grid-cols-2">
      {columns.map((column) => <section key={column.id} id={column.id} aria-labelledby={`${column.id}-title`} className="space-y-6">
        <h2 id={`${column.id}-title`} className="text-2xl font-bold tracking-tight md:text-3xl">{column.title}</h2>
        {column.id === "returns" && !currentCustomerPolicies() && <p className="rounded-lg border p-4 text-sm" role="note">{POLICY_DRAFT_NOTICE}</p>}
        {column.items.map(({ icon: Icon, title, description }) => <div key={title} className="flex items-start gap-3">
          <div className="mt-1 rounded-md bg-muted p-2"><Icon aria-hidden="true" className="size-5 text-muted-foreground" /></div>
          <div className="min-w-0">
            <h3 className="text-lg font-medium">{title}</h3>
            <p className="mt-1 text-muted-foreground">{description}</p>
          </div>
        </div>)}
      </section>)}
    </div>

    <nav aria-labelledby="policies-title" className="mt-12 border-t pt-8">
      <h2 id="policies-title" className="font-semibold">Full policies</h2>
      <ul className="mt-2 flex flex-wrap gap-x-6">
        {policies.map((policy) => <li key={policy.href}><Link href={policy.href} className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">{policy.label}</Link></li>)}
      </ul>
    </nav>

    <section id="contact" aria-labelledby="contact-title" className="mt-16 border-t pt-12">
      <h2 id="contact-title" className="text-2xl font-bold tracking-tight md:text-3xl">Contact us</h2>
      <p className="mt-2 text-muted-foreground">Questions about a piece, delivery, collection or an order.</p>
      <div className="mt-6 grid grid-cols-1 divide-y md:grid-cols-3 md:divide-x md:divide-y-0">
        <div className="flex gap-4 py-6 md:pr-6">
          <MapPin aria-hidden="true" className="mt-1 size-6 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <h3 className="font-semibold">Showroom</h3>
            <address className="mt-1 text-sm not-italic">{SHOWROOM.address}</address>
            <p className="mt-1 text-sm text-muted-foreground">{SHOWROOM.note}</p>
            <table className="mt-3 text-sm">
              <tbody>{SHOWROOM.hours.map((row) => <tr key={row.days}>
                <th scope="row" className="py-0.5 pr-6 text-left font-normal text-muted-foreground">{row.days}</th>
                <td className="py-0.5 font-medium whitespace-nowrap tabular-nums">{row.time}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>
        <div className="flex gap-4 py-6 md:px-6">
          <Phone aria-hidden="true" className="mt-1 size-6 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <h3 className="font-semibold">Phone</h3>
            <ul className="mt-1 text-sm">{SHOWROOM.phones.map((phone) => <li key={phone.number}>
              {phone.label}: <a href={`tel:${phone.number.replace(/[^+\d]/g, "")}`} className="inline-flex min-h-11 items-center font-medium underline underline-offset-4">{phone.number}</a>
            </li>)}</ul>
          </div>
        </div>
        <div className="flex gap-4 py-6 md:pl-6">
          <Mail aria-hidden="true" className="mt-1 size-6 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <h3 className="font-semibold">Email</h3>
            <p className="mt-1 text-sm text-muted-foreground">For questions about a piece or an order.</p>
            <p className="mt-1 text-sm font-medium break-all">{SHOWROOM.email}</p>
          </div>
        </div>
      </div>
    </section>
  </div>;
}
