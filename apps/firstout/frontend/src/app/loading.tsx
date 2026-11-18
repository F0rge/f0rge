"use client";

import { usePathname } from "next/navigation";
import { AuthPageLoading } from "@/components/auth-loading";
import { PageLoading } from "@/components/page-loading";

export default function Loading() {
  const pathname = usePathname();
  return <AuthPageLoading pathname={pathname} fallback={<PageLoading kind="status" />} />;
}
