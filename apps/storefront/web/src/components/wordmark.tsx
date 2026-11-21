import { cn } from "@f0rge/ui";

export function Wordmark({ className }: { className?: string }) {
  return <span className={cn("font-serif font-normal leading-none whitespace-nowrap", className)}>DasKasas</span>;
}
