import Link from "next/link";
import type { PolicyView } from "@/lib/customer-policies";

function withPlaceholders(text: string) {
  const parts = text.split(/(\[PLACEHOLDER:[^\]]+\])/g);
  return parts.map((part, index) => part.startsWith("[PLACEHOLDER:")
    ? <span key={`${index}-${part.slice(0, 24)}`} className="bg-amber-100 px-0.5 text-foreground">{part}</span>
    : <span key={`${index}-text`}>{part}</span>);
}

export function PolicyArticle({ page, section }: { page: PolicyView; section: string }) {
  return <article className="mx-auto w-full max-w-3xl px-4 py-10 break-words md:px-6 md:py-16">
    <h1 className="text-3xl font-bold tracking-tight md:text-4xl">{page.title}</h1>
    {page.blocks.map((block, index) => {
      if (block.type === "notice") return <p key={`${section}-notice-${index}`} className="mt-6 rounded-lg border p-4 text-sm" role="note">{block.text}</p>;
      if (block.type === "heading") return <h2 key={`${section}-heading-${index}`} className="mt-10 text-xl font-semibold">{block.text}</h2>;
      return <p key={`${section}-paragraph-${index}`} className="mt-4 leading-relaxed text-muted-foreground">{withPlaceholders(block.text)}</p>;
    })}
    {page.links.length > 0 && <nav className="mt-10 flex flex-wrap gap-x-6 border-t pt-6" aria-label="Related policies">
      {page.links.map((link) => <Link key={link.href} href={link.href} className="inline-flex min-h-11 items-center text-sm font-medium underline underline-offset-4">{link.label}</Link>)}
    </nav>}
  </article>;
}
