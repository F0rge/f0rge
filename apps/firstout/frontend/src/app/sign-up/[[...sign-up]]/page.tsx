import Link from "next/link";
import { ClerkStaffSignUp } from "@/components/staff-provider";

export default function SignUpPage() {
  return (
    <div className="firstout-login-page">
      <section className="firstout-login-card firstout-auth-card">
        <h1 className="cds--type-productive-heading-04">Create your organisation</h1>
        <p className="cds--type-body-01">Start free with up to five staff members. Verify your email, then set up your business.</p>
        <ClerkStaffSignUp />
        <Link href="/clerk-login" className="cds--link">Already have an account? Sign in</Link>
        <Link href="/login" className="cds--link">Use existing Firstout login</Link>
      </section>
    </div>
  );
}
