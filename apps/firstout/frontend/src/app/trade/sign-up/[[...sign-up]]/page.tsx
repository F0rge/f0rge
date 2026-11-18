import { AuthPageLoading } from "@/components/auth-loading";
import { Suspense } from "react";
import { TradeAuthentication } from "@/components/trade-authentication";

export default function TradeSignUpPage() {
  return <Suspense fallback={<AuthPageLoading pathname="/trade/sign-up" />}><TradeAuthentication mode="sign-up" /></Suspense>;
}
