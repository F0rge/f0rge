import { PageLoading } from "@/components/page-loading";
import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeLoginPage() {
  return <Suspense fallback={<PageLoading label="Loading sign-in…" />}><TradeAuthentication mode="login" /></Suspense>;
}
