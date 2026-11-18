"use client";

import { SignIn, SignUp, useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { AuthPageLoading, ClerkAuthCard, ClerkSignInLoading, ClerkWidgetLoading } from "@/components/auth-loading";
import { tradeAuthUrl, tradeReturnPath } from "@/lib/trade-auth";

export function TradeAuthentication({ mode }: { mode: "login" | "sign-up" }) {
  const { isLoaded, isSignedIn } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const search = useSearchParams();
  const returnPath = tradeReturnPath(search.get("redirect_url"));
  useEffect(() => { if (isLoaded && isSignedIn) router.replace(returnPath); }, [isLoaded, isSignedIn, returnPath, router]);
  if (!isLoaded) return <AuthPageLoading pathname={pathname} />;
  if (isSignedIn) return <Link className="cds--link" href={returnPath}>Continue to trade portal</Link>;
  return (
    <ClerkAuthCard kind={mode === "login" ? "trade-login" : "trade-sign-up"}>
      {mode === "login" ? (
        <SignIn
          routing="path"
          path="/trade/login"
          forceRedirectUrl={returnPath}
          signUpForceRedirectUrl={returnPath}
          signUpUrl={tradeAuthUrl("sign-up", returnPath)}
          fallback={<ClerkSignInLoading pathname={pathname} />}
        />
      ) : (
        <SignUp
          routing="path"
          path="/trade/sign-up"
          forceRedirectUrl={returnPath}
          signInForceRedirectUrl={returnPath}
          signInUrl={tradeAuthUrl("login", returnPath)}
          fallback={<ClerkWidgetLoading mode="sign-up" />}
        />
      )}
    </ClerkAuthCard>
  );
}
