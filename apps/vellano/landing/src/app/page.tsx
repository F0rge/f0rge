import { ChainMarquee } from "@/components/chain-marquee";
import { CtaBand } from "@/components/cta-band";
import { Faq } from "@/components/faq";
import { Hero } from "@/components/hero";
import { Highlights } from "@/components/highlights";
import { OnboardingSteps } from "@/components/onboarding-steps";
import { Pillars } from "@/components/pillars";
import { SouthAfrica } from "@/components/south-africa";

export default function HomePage() {
  return (
    <>
      <Hero />
      <ChainMarquee />
      <Pillars />
      <SouthAfrica />
      <OnboardingSteps />
      <Highlights />
      <Faq />
      <CtaBand />
    </>
  );
}
