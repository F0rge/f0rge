import Link from "next/link";
import { ClerkStaffSignIn } from "@/components/staff-provider";

export default function ClerkLoginPage() {
  return (
    <div className="firstout-login-page">
      <section className="firstout-login-card">
        <h1 className="cds--type-productive-heading-04">
          Organisation sign-in
        </h1>
        <ClerkStaffSignIn />
        <Link href="/login" className="cds--link">
          Use existing Firstout login
        </Link>
      </section>
    </div>
  );
}
