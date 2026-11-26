import type { Metadata } from "next";
import { publicPageMetadata } from "@/lib/storefront-metadata";
import { Listing } from "./listing";

export const dynamic = "force-dynamic";
export const metadata: Metadata = publicPageMetadata({
  title: "Shop furniture",
  description: "Browse sofas and armchairs, dining and bedroom furniture, and coffee and console tables at DasKasas. Filter by price and availability.",
  path: "/shop",
});

export default function ShopPage() {
  return <Listing />;
}
