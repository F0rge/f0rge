"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function safeHref(href: string | undefined): string | undefined {
  if (!href) {
    return undefined;
  }
  const trimmed = href.trim();
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("/")) {
    return trimmed;
  }
  return undefined;
}

const COMPONENTS: Components = {
  a({ href, children }) {
    const safe = safeHref(href);
    if (!safe) {
      return <span>{children}</span>;
    }
    return (
      <a href={safe} target="_blank" rel="noreferrer noopener">
        {children}
      </a>
    );
  },
};

type NiaMarkdownProps = {
  text: string;
};

/** Assistant-only markdown. Raw HTML is not rendered (no rehype-raw). */
export function NiaMarkdown({ text }: NiaMarkdownProps) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={COMPONENTS}>
      {text}
    </ReactMarkdown>
  );
}
