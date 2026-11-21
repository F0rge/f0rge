import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Plus, Minus, CreditCard, Package } from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, type Route } from '@/lib/router';

export interface CompactCartItem {
  id: string;
  name: string;
  /** Second line, e.g. "Dining Room · 2 in stock". */
  detail: string;
  /** Line price as display text. */
  price: string;
  quantity: number;
  /** Stock: the + button stops here. */
  max?: number;
  image: ReactNode;
}

export interface CompactCartProps {
  items: CompactCartItem[];
  totalItems: number;
  onQuantityChange: (id: string, quantity: number) => void;
  onRemove: (id: string) => void;
  title: string;
  emptyText: string;
  summaryTitle: string;
  subtotal: string;
  deliveryCost: string;
  total: string;
  /** Small line under the total. */
  totalNote?: string;
  /** Replaces the demo's free-shipping line. */
  note: string;
  action: { label: string; to: Route };
}

// The demo wraps this in a default-open <Sheet> with a cart trigger button inside a
// fixed 850px box ("for example purpose only"). Here it is the checkout page's order
// summary, so the sheet's content renders in place; SheetHeader/Title/Description
// become plain elements carrying the same classes (they need a Dialog context).
export default function CompactCart({
  items,
  totalItems,
  onQuantityChange,
  onRemove,
  title,
  emptyText,
  summaryTitle,
  subtotal,
  deliveryCost,
  total,
  totalNote,
  note,
  action,
}: CompactCartProps) {
  return (
    <>
      <div className="w-full">
        <div className="flex flex-col gap-1.5 p-4">
          <h2 className="font-heading text-foreground font-medium">{title}</h2>
          <p className="text-muted-foreground text-sm">
            {totalItems} {totalItems === 1 ? 'item' : 'items'} in your bag
          </p>
        </div>

        <div className="mt-6 space-y-6">
          {/* Cart Items */}
          <div className="space-y-4">
            {items.length === 0 && (
              <p className="text-muted-foreground px-4 text-sm">{emptyText}</p>
            )}
            {items.map((item) => (
              <Card key={item.id} className="overflow-hidden p-0">
                <CardContent className="p-0">
                  <div className="flex">
                    {/* Product Image */}
                    <div className="relative h-auto w-24 flex-shrink-0">
                      {item.image}
                    </div>

                    {/* Product Details */}
                    <div className="flex-1 p-4">
                      <div className="flex justify-between">
                        <div>
                          <h3 className="text-sm font-medium">{item.name}</h3>
                          <p className="text-muted-foreground text-xs">
                            {item.detail}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => onRemove(item.id)}
                          aria-label={`Remove ${item.name}, ${item.detail}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="mt-2 flex items-center justify-between">
                        <div className="flex items-center gap-1">
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() =>
                              onQuantityChange(item.id, Math.max(1, item.quantity - 1))
                            }
                            aria-label="Decrease quantity"
                          >
                            <Minus className="h-3 w-3" />
                          </Button>
                          <span className="w-6 text-center text-sm">
                            {item.quantity}
                          </span>
                          <Button
                            variant="outline"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => onQuantityChange(item.id, item.quantity + 1)}
                            disabled={item.max !== undefined && item.quantity >= item.max}
                            aria-label="Increase quantity"
                          >
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>

                        <div className="text-right">
                          <div className="text-sm font-medium">{item.price}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Order Summary */}
          <Card className="gap-0 p-0">
            <CardHeader className="p-4">
              <CardTitle className="text-lg">{summaryTitle}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 p-4 pt-0">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Subtotal</span>
                  <span>{subtotal}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Delivery</span>
                  <span>{deliveryCost}</span>
                </div>
                <div className="flex justify-between font-medium">
                  <span>Total</span>
                  <span>{total}</span>
                </div>
                {totalNote && <p className="text-muted-foreground text-xs">{totalNote}</p>}
              </div>

              <div className="text-muted-foreground flex items-center gap-2 text-sm">
                <Package className="h-4 w-4" />
                <span>{note}</span>
              </div>

              <Button className="w-full" asChild>
                <Link to={action.to}>
                  <CreditCard className="mr-2 h-4 w-4" />
                  {action.label}
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
