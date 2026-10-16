import Link from "next/link";
import type { PolicyView } from "@/lib/customer-policies";

function withPlaceholders(text: string) {
  const parts = text.split(/(\[PLACEHOLDER:[^\]]+\])/g);
  return parts.map((part, index) => part.startsWith("[PLACEHOLDER:")
    ? <span key={`${index}-${part.slice(0, 24)}`} className="policy-placeholder">{part}</span>
    : <span key={`${index}-text`}>{part}</span>);
}

export function PolicyArticle({ page, section }: { page: PolicyView; section: string }) {
  return <article className="content policy-page">
    <p className="eyebrow">Vellano</p>
    <h1>{page.title}</h1>
    {page.blocks.map((block, index) => {
      if (block.type === "notice") return <p key={`${section}-notice-${index}`} className="policy-draft-notice" role="note">{block.text}</p>;
      if (block.type === "heading") return <h2 key={`${section}-heading-${index}`}>{block.text}</h2>;
      return <p key={`${section}-paragraph-${index}`}>{withPlaceholders(block.text)}</p>;
    })}
    {page.links.length > 0 && <nav className="policy-related" aria-label="Related policies">
      {page.links.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}
    </nav>}
  </article>;
}
