import Link from "next/link";
import { IMPORTANT_TERMS, IMPORTANT_TERMS_PURPOSE } from "@/lib/customer-policies";

export const TERMS_ACCEPTANCE_ID = "checkout-terms-acceptance";

// CPA s49(4)(b): the important terms are drawn to the customer's attention before they pay, in plain language (s22, s49(3)).
export function BeforeYouPay() {
  return <section aria-labelledby="before-you-pay-heading" className="space-y-3 rounded-lg border-2 border-foreground p-4 text-sm font-normal">
    <h2 id="before-you-pay-heading" className="text-base font-medium">Before you pay</h2>
    <p>{`Please read these points. ${IMPORTANT_TERMS_PURPOSE}`}</p>
    <ul className="list-disc space-y-1 pl-5">{IMPORTANT_TERMS.map((term) => <li key={term}>{term}</li>)}</ul>
    <p>None of these points reduces your rights under consumer law. <Link href="/policies/terms" className="font-medium underline underline-offset-4">Read our full terms of sale</Link></p>
    <p id={TERMS_ACCEPTANCE_ID} className="font-medium">By continuing you accept our terms of sale.</p>
  </section>;
}
