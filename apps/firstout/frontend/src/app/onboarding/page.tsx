"use client";

import Image from "next/image";
import { Theme, Stack } from "@carbon/react";
import { clerkEnabled } from "@/components/staff-provider";
import { OrganisationOnboarding } from "@/components/organisation-onboarding";

// Superdesign draft attempted; its API was unavailable (DNS resolution failure).
export default function OnboardingPage() {
  return <Theme theme="g10"><main className="firstout-onboarding-page">
    <section className="firstout-onboarding-content"><Stack gap={7}>
      <header><Stack gap={4}>
        <Image src="/brand/logo-transparent.png" alt="Firstout" width={72} height={72} />
        <h1 className="cds--type-productive-heading-05">Your business, ready to work</h1>
        <p className="cds--type-body-02">Create a free organisation or open one you already belong to.</p>
      </Stack></header>
      {clerkEnabled ? <OrganisationOnboarding /> : <p>Organisation signup is not enabled yet.</p>}
    </Stack></section>
  </main></Theme>;
}
