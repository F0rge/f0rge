import type { Metadata } from "next";
import { Listing } from "./listing";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Shop furniture",
  description: "Browse sofas and armchairs, dining and bedroom furniture, and coffee and console tables at DasKasas. Filter by price and availability.",
  alternates: { canonical: "/shop" },
};

export default function ShopPage() {
  return <Listing />;
}
