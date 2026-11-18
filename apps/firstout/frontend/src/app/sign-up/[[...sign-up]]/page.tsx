import { ClerkAuthCard } from "@/components/auth-loading";
import { ClerkStaffSignUp } from "@/components/staff-provider";

export default function SignUpPage() {
  return (
    <ClerkAuthCard kind="staff-sign-up">
      <ClerkStaffSignUp />
    </ClerkAuthCard>
  );
}
