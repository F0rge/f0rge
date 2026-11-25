import type { Metadata } from "next";
import { Listing } from "./listing";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Shop furniture",
  description: "Browse the DasKasas furniture collection, from sofas and armchairs to dining tables, bedroom furniture, and coffee and console tables.",
  alternates: { canonical: "/shop" },
};

export default function ShopPage() {
  return <Listing />;
}
