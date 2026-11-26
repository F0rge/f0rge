import { canonicalUrl, storefrontIndexable } from "@/lib/launch-indexing";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { SHOWROOM } from "@/lib/showroom";

export const dynamic = "force-dynamic";

export function GET(): Response {
  const base = process.env.NEXT_PUBLIC_BASE_URL;
  const headers = { "Cache-Control": "no-store" };
  if (!base || !storefrontIndexable()) return new Response(null, { status: 404, headers });

  const link = (name: string, path: string) => `- [${name}](${canonicalUrl(base, path)})`;
  const text = [
    "# DasKasas",
    "",
    "> DasKasas is a furniture store in Bedfordview with an online shop and a showroom at Bedford Square.",
    "",
    `Visit the showroom at ${SHOWROOM.address}. ${SHOWROOM.note}`,
    "",
    "## Shop",
    "",
    link("Shop all furniture", "/shop"),
    ...SHOP_CATEGORIES.map(({ name, href }) => link(name, href)),
    "",
    "## Showroom and help",
    "",
    link("Showroom hours, contact and help", "/help"),
    link("Delivery and collection policy", "/policies/delivery"),
    link("Return policy", "/policies/returns"),
    link("Refund policy", "/policies/refunds"),
    "",
  ].join("\n");

  return new Response(text, { headers: { ...headers, "Content-Type": "text/plain; charset=utf-8" } });
}
