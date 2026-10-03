import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Sign in", robots: { index: false, follow: false, noarchive: true } };

export default function SignInPage() {
  const configured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  if (!configured) return <div className="content account-page" data-storefront-no-capture=""><p className="eyebrow">Customer sign-in</p><h1>Sign-in is temporarily unavailable</h1><p>Guest shopping and checkout are still available.</p></div>;
  return <div className="content account-page" data-storefront-no-capture=""><p className="eyebrow">The Collector / customer account</p><h1>Sign in or create an account</h1><p className="checkout-intro">Use the passwordless email option to save and reuse your delivery addresses.</p><div style={{ marginTop: "2rem" }}><SignIn forceRedirectUrl="/account" signUpForceRedirectUrl="/account" /></div></div>;
}
