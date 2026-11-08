import { ClerkStaffSignIn } from "@/components/staff-provider";

export default function ClerkLoginPage() {
  return (
    <div className="firstout-login-page">
      <section className="firstout-login-card firstout-auth-card">
        <h1 className="cds--type-productive-heading-04">
          Organisation sign-in
        </h1>
        <ClerkStaffSignIn />
      </section>
    </div>
  );
}
