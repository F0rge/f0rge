import type { Metadata } from "next";
import { SignUp } from "@clerk/nextjs";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Create account", robots: { index: false, follow: false, noarchive: true } };

export default function SignUpPage() {
  const configured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  if (!configured) return <div className="content account-page" data-storefront-no-capture=""><p className="eyebrow">Customer sign-up</p><h1>Sign-up is temporarily unavailable</h1><p>Guest shopping and checkout are still available.</p></div>;
  return <div className="content account-page" data-storefront-no-capture=""><p className="eyebrow">The Collector / customer account</p><h1>Create an account</h1><p className="checkout-intro">Use a one-time email code to save delivery addresses. You can still shop as a guest.</p><div style={{ marginTop: "2rem" }}><SignUp forceRedirectUrl="/account" signInForceRedirectUrl="/account" /></div></div>;
}
