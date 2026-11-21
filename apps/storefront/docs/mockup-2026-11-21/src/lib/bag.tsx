import { createContext, useContext, useState, type ReactNode } from 'react';
import { pieces, type Piece } from '@/content';

export interface BagLine {
  sku: string;
  qty: number;
}

export interface BagItem extends BagLine {
  piece: Piece;
  lineTotal: number;
}

interface Bag {
  lines: BagLine[];
  /** Lines joined with their catalogue piece. */
  items: BagItem[];
  count: number;
  /** Rand, VAT included. Delivery is not included. */
  subtotal: number;
  /** Adds, capped at the piece's stock. */
  add: (sku: string, qty?: number) => void;
  /** Sets the quantity, capped at stock; below 1 removes the line. */
  setQty: (sku: string, qty: number) => void;
  remove: (sku: string) => void;
  /** The navbar's bag drawer (sidebar-cart block). */
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
}

const BagContext = createContext<Bag | null>(null);
const stockOf = (sku: string) => pieces.find((p) => p.sku === sku)?.stock ?? 0;

// ponytail: only catalogue pieces go in the bag; the Arc sofa is enquiry-only.
export function BagProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<BagLine[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const setQty = (sku: string, qty: number) =>
    setLines((prev) => {
      const capped = Math.min(qty, stockOf(sku));
      if (capped < 1) return prev.filter((l) => l.sku !== sku);
      return prev.some((l) => l.sku === sku)
        ? prev.map((l) => (l.sku === sku ? { ...l, qty: capped } : l))
        : [...prev, { sku, qty: capped }];
    });
  const add = (sku: string, qty = 1) =>
    setQty(sku, (lines.find((l) => l.sku === sku)?.qty ?? 0) + qty);
  const remove = (sku: string) => setLines((prev) => prev.filter((l) => l.sku !== sku));

  const items = lines.flatMap((l) => {
    const piece = pieces.find((p) => p.sku === l.sku);
    return piece ? [{ ...l, piece, lineTotal: piece.price * l.qty }] : [];
  });
  const count = lines.reduce((n, l) => n + l.qty, 0);
  // Sum in cents to avoid float drift.
  const subtotal = items.reduce((cents, i) => cents + Math.round(i.piece.price * 100) * i.qty, 0) / 100;

  return (
    <BagContext.Provider
      value={{ lines, items, count, subtotal, add, setQty, remove, drawerOpen, setDrawerOpen }}
    >
      {children}
    </BagContext.Provider>
  );
}

export function useBag() {
  const bag = useContext(BagContext);
  if (!bag) throw new Error('useBag needs <BagProvider>');
  return bag;
}
