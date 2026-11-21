import type { Metadata } from "next";
import { SignIn } from "@clerk/nextjs";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Sign in", robots: { index: false, follow: false, noarchive: true } };

export default function SignInPage() {
  const configured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  if (!configured) return <div className="mx-auto w-full max-w-md space-y-2 px-4 py-10 md:px-6" data-storefront-no-capture=""><h1 className="text-2xl font-semibold">Sign-in is temporarily unavailable</h1><p className="text-muted-foreground">Guest shopping and checkout are still available.</p></div>;
  return <div className="mx-auto w-full max-w-md px-4 py-10 md:px-6" data-storefront-no-capture=""><h1 className="text-2xl font-semibold">Sign in or create an account</h1><p className="mt-2 text-muted-foreground">Use the passwordless email option to save and reuse your delivery addresses.</p><div className="mt-8 flex min-w-0 justify-center"><SignIn forceRedirectUrl="/account" signUpForceRedirectUrl="/account" /></div></div>;
}
