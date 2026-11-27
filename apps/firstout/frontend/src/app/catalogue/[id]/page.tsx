"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { PageLoading } from "@/components/page-loading";
import { skuPanelSearch } from "@/lib/sku-panel";

/**
 * `/catalogue/{id}` stays a working link (bookmarks, SkuLink new tabs, the archive dialog, search):
 * it opens the catalogue with that SKU in the full view, where everything is read and edited.
 */
export default function SkuDeepLinkPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/catalogue?${skuPanelSearch("", { id, view: "full" })}`);
  }, [id, router]);
  return <PageLoading label="Opening SKU…" />;
}
