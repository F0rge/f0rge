"use client";

import { SignIn, SignUp, useAuth } from "@clerk/nextjs";
import { Loading } from "@carbon/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { tradeAuthUrl, tradeReturnPath } from "@/lib/trade-auth";

export function TradeAuthentication({ mode }: { mode: "login" | "sign-up" }) {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const search = useSearchParams();
  const returnPath = tradeReturnPath(search.get("redirect_url"));
  useEffect(() => { if (isLoaded && isSignedIn) router.replace(returnPath); }, [isLoaded, isSignedIn, returnPath, router]);
  if (!isLoaded) return <Loading withOverlay={false} description="Loading sign-in…" />;
  if (isSignedIn) return <Link className="cds--link" href={returnPath}>Continue to trade portal</Link>;
  return <div className="firstout-login-page"><section className="firstout-login-card firstout-auth-card">
    <h1 className="cds--type-productive-heading-04">Trade customer {mode === "login" ? "sign-in" : "sign-up"}</h1>
    <p className="cds--type-body-01">Use the email on your trade invitation. Access is approved separately by the business.</p>
    {mode === "login" ? <SignIn routing="path" path="/trade/login" forceRedirectUrl={returnPath} signUpForceRedirectUrl={returnPath} signUpUrl={tradeAuthUrl("sign-up", returnPath)} /> :
      <SignUp routing="path" path="/trade/sign-up" forceRedirectUrl={returnPath} signInForceRedirectUrl={returnPath} signInUrl={tradeAuthUrl("login", returnPath)} />}
  </section></div>;
}
