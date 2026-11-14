"use client";

import Image from "next/image";
import { Theme, Stack } from "@carbon/react";
import { clerkEnabled } from "@/components/staff-provider";
import { OrganisationOnboarding } from "@/components/organisation-onboarding";

// Superdesign draft attempted; its API was unavailable (DNS resolution failure).
export default function OnboardingPage() {
  return <Theme theme="g10"><main className="firstout-onboarding-page">
    <section className="firstout-onboarding-content"><Stack gap={7}>
      <header className="firstout-onboarding-header">
        <Image src="/brand/logo-transparent.png" alt="Firstout" width={48} height={48} />
        <Stack gap={3}>
          <h1 className="cds--type-productive-heading-04">Choose your business</h1>
          <p className="cds--type-body-02">Your team, stock and books, in one workspace.</p>
        </Stack>
      </header>
      {clerkEnabled ? <OrganisationOnboarding /> : <p>Organisation signup is not enabled yet.</p>}
    </Stack></section>
  </main></Theme>;
}
