import type { ReactNode } from "react";

export function MotionProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function Reveal({
  children,
  className = "",
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "li" | "section" | "article";
}) {
  const Tag = as;
  return <Tag className={className}>{children}</Tag>;
}
