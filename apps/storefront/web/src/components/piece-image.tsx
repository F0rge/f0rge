import { cn } from "@f0rge/ui";
import type { StoreProduct } from "@/lib/medusa";

// A neat named tile wherever a piece has no photograph yet.
export function PieceImage({ product, className }: { product: StoreProduct; className?: string }) {
  const image = product.thumbnail || product.images?.[0]?.url;
  return image
    ? <img src={image} alt="" width={800} height={800} loading="lazy" className={cn("size-full object-cover transition-transform group-hover:scale-105", className)} />
    : <div aria-hidden="true" data-placeholder className={cn("flex size-full min-h-24 items-center justify-center bg-muted p-4 text-center", className)}><span className="text-xs text-muted-foreground">{product.title}</span></div>;
}
