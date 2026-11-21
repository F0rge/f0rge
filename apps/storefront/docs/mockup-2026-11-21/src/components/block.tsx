import type { ReactNode } from 'react';

interface BlockProps {
  /** `<category>/<block>` on shadcn-ui-blocks.com, or a short id for Original sections. */
  name: string;
  collection?: 'ecommerce' | 'marketing';
  original?: boolean;
  children: ReactNode;
}

/** Marks which free block (or Original section) a section is. Renders nothing extra. */
export function Block({ children }: BlockProps) {
  return <>{children}</>;
}
