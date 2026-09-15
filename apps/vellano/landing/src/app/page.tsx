import { CompanySetup } from "@/components/company-setup";
import { CtaBand } from "@/components/cta-band";
import { Faq } from "@/components/faq";
import { Hero } from "@/components/hero";
import { Highlights } from "@/components/highlights";
import { Isolation } from "@/components/isolation";
import { Limits } from "@/components/limits";
import { OnboardingSteps } from "@/components/onboarding-steps";
import { Pillars } from "@/components/pillars";
import { SaleMoves } from "@/components/sale-moves";
import { SouthAfrica } from "@/components/south-africa";

export default function HomePage() {
  return (
    <>
      <Hero />
      <SaleMoves />
      <Pillars />
      <Isolation />
      <CompanySetup />
      <SouthAfrica />
      <OnboardingSteps />
      <Highlights />
      <Limits />
      <Faq />
      <CtaBand />
    </>
  );
}
