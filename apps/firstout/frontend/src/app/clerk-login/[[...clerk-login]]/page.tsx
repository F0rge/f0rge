import { ClerkAuthCard } from "@/components/auth-loading";
import { ClerkStaffSignIn } from "@/components/staff-provider";

export default function ClerkLoginPage() {
  return (
    <ClerkAuthCard kind="staff-login">
      <ClerkStaffSignIn />
    </ClerkAuthCard>
  );
}
