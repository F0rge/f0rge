import type { Metadata } from "next";
import Link from "next/link";
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from "@f0rge/ui";
import { getCustomerContext } from "@/lib/customer-auth";
import { AccountClient } from "./account-client";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Your account",
  description: "View your DasKasas orders and manage your saved delivery addresses.",
  robots: { index: false, follow: false, noarchive: true },
};

export default async function AccountPage() {
  let customer: { email: string; first_name: string; last_name: string } | null = null;
  let unavailable = false;
  try {
    const context = await getCustomerContext();
    if (context) customer = { email: context.email, first_name: context.first_name, last_name: context.last_name };
  } catch { unavailable = true; }

  return <div className="mx-auto w-full max-w-7xl px-4 py-10 md:px-6">
    <h1 className="text-2xl font-semibold">Your account</h1>
    {unavailable ? <p role="alert" className="mt-6 rounded-lg border border-destructive p-4 text-sm text-destructive">Customer sign-in is temporarily unavailable. Please try again later or continue shopping as a guest.</p>
      : customer ? <AccountClient customer={customer} />
        : <Card className="mt-6 max-w-xl">
          <CardHeader>
            <CardTitle><h2 className="text-xl">Sign in to your account</h2></CardTitle>
            <CardDescription>Use a one-time email code to manage your saved delivery addresses. You can always shop and check out as a guest.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm font-medium">
            <Button className="h-11 px-4" nativeButton={false} role="link" render={<Link href="/account/sign-in" />}>Continue with email</Button>
          </CardContent>
        </Card>}
  </div>;
}
