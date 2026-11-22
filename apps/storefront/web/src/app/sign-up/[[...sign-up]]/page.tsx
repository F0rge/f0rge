import type { Metadata } from "next";
import Link from "next/link";
import { SignUp } from "@clerk/nextjs";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Create account", robots: { index: false, follow: false, noarchive: true } };

export default function SignUpPage() {
  const configured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY && process.env.STOREFRONT_CLERK_JWT_TEMPLATE);
  if (!configured) return <div className="mx-auto w-full max-w-md space-y-2 px-4 py-10 md:px-6"><h1 className="text-2xl font-semibold">Sign-up is temporarily unavailable</h1><p className="text-muted-foreground">Guest shopping and checkout are still available.</p></div>;
  return <div className="mx-auto w-full max-w-md px-4 py-10 md:px-6"><h1 className="text-2xl font-semibold">Create an account</h1><p className="mt-2 text-muted-foreground">Use a one-time email code to save delivery addresses. You can still shop as a guest.</p>{/* POPIA s18(2)(a): short notice before Clerk collects the email. */}<p className="mt-2 text-sm text-muted-foreground">Clerk, our sign-in provider in the United States, receives your email address to send the code. We use your account for saved addresses and your orders. <Link href="/policies/privacy" className="font-medium text-foreground underline underline-offset-4">Our privacy policy</Link> explains your rights, including the right to object.</p><div className="mt-8 flex min-w-0 justify-center"><SignUp forceRedirectUrl="/account" signInForceRedirectUrl="/account" /></div></div>;
}
