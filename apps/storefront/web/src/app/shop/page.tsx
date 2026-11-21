import type { Metadata } from "next";
import { Listing } from "./listing";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Shop furniture", description: "Discover DasKasas's considered furniture collection.", alternates: { canonical: "/shop" } };

export default function ShopPage() {
  return <Listing />;
}
