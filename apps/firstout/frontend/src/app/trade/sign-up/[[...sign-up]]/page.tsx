import { PageLoading } from "@/components/page-loading";
import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeSignUpPage() {
  return <Suspense fallback={<PageLoading label="Loading sign-up…" />}><TradeAuthentication mode="sign-up" /></Suspense>;
}
