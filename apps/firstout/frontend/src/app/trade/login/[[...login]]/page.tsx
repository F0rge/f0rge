import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeLoginPage() {
  return <Suspense fallback={<p>Loading sign-in…</p>}><TradeAuthentication mode="login" /></Suspense>;
}
