import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeSignUpPage() {
  return <Suspense fallback={<p>Loading sign-up…</p>}><TradeAuthentication mode="sign-up" /></Suspense>;
}
