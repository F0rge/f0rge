import type { Metadata } from "next";
import Link from "next/link";
import { getCustomerContext } from "@/lib/customer-auth";
import { AccountClient } from "./account-client";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Your account", robots: { index: false, follow: false, noarchive: true } };

export default async function AccountPage() {
  let customer: { email: string; first_name: string; last_name: string } | null = null;
  let unavailable = false;
  try {
    const context = await getCustomerContext();
    if (context) customer = { email: context.email, first_name: context.first_name, last_name: context.last_name };
  } catch { unavailable = true; }

  return <div className="content account-page">
    <p className="eyebrow">The Collector / customer account</p>
    <h1>Your account</h1>
    {unavailable ? <p role="alert" className="account-error">Customer sign-in is temporarily unavailable. Please try again later or continue shopping as a guest.</p>
      : customer ? <AccountClient customer={customer} />
        : <section className="account-panel">
          <h2>Sign in to your account</h2>
          <p>Use a one-time email code to manage your saved delivery addresses. You can always shop and check out as a guest.</p>
          <Link className="account-primary" href="/account/sign-in">Continue with email ↗</Link>
        </section>}
  </div>;
}
