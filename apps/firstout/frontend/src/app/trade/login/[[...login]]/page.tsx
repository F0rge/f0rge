import { AuthPageLoading } from "@/components/auth-loading";
import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeLoginPage() {
  return <Suspense fallback={<AuthPageLoading pathname="/trade/login" />}><TradeAuthentication mode="login" /></Suspense>;
}
