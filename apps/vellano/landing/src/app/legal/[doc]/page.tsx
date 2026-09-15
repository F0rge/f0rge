import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { site } from "@/lib/site";

const docs = {
  privacy: {
    title: "Privacy notice",
    body: [
      `${site.name} provides back-office software to companies. When a company creates a workspace, that company is the responsible party for the personal information it processes (its customers, suppliers, and staff). ${site.operatorName} processes that information only on the company's instructions, as an operator.`,
      "We collect, for the platform itself: the owner's name and work email, the company's legal and trading names, the workspace address chosen, IP address and browser details at signup, and the acknowledgements ticked on the signup form.",
      "Hosting is outside South Africa on managed infrastructure in the United States. Data is encrypted in transit and at rest. Each company's operational data is kept in its own database.",
      "You may ask for access, correction, or deletion of your platform account details at the support address below. Deleting a company workspace removes its database after a 30-day hold.",
    ],
  },
  popia: {
    title: "POPIA notice",
    body: [
      "Under the Protection of Personal Information Act 4 of 2013, each company using the software is the responsible party for personal information inside its workspace. We are the operator.",
      "Section 72 — transfers outside the Republic: information is stored and processed outside South Africa. By creating a workspace the company's authorised representative consents to this transfer on the company's behalf and undertakes to inform its own data subjects where required.",
      "Section 19–21 — security and operator agreement: we maintain reasonable technical and organisational measures and will enter into a written operator agreement with any company that requests one.",
      "Section 22 — breach notification: we notify affected companies without undue delay so they can notify the Regulator and their data subjects.",
    ],
  },
  terms: {
    title: "Terms",
    body: [
      "The service is provided to companies, not consumers. The person creating a workspace confirms they are authorised to bind the company.",
      "There is currently no charge. We will give at least 60 days' notice before pricing applies to an existing workspace.",
      "Workspaces that stay empty for 90 days after creation may be removed after an email warning.",
      "These terms are governed by the laws of the Republic of South Africa.",
    ],
  },
} as const;

type Doc = keyof typeof docs;

export function generateStaticParams() {
  return (Object.keys(docs) as Doc[]).map((doc) => ({ doc }));
}

export async function generateMetadata({ params }: { params: Promise<{ doc: string }> }): Promise<Metadata> {
  const { doc } = await params;
  const entry = docs[doc as Doc];
  return { title: entry ? entry.title : "Legal" };
}

export default async function LegalPage({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  const entry = docs[doc as Doc];
  if (!entry) notFound();
  return (
    <article className="mx-auto max-w-2xl px-5 py-20 sm:px-8 sm:py-28">
      <div className="inline-flex items-center gap-2 border border-line bg-paper-2 px-3 py-1 text-xs text-muted">
        Draft · version {site.privacyVersion} · legal review pending
      </div>
      <h1 className="mt-6 font-serif text-4xl leading-tight sm:text-5xl">{entry.title}</h1>
      <div className="mt-8 space-y-5 text-base leading-relaxed text-ink-2">
        {entry.body.map((p) => (
          <p key={p.slice(0, 32)}>{p}</p>
        ))}
      </div>
      <p className="mt-10 text-sm text-muted">Questions: {site.supportEmail}</p>
    </article>
  );
}
