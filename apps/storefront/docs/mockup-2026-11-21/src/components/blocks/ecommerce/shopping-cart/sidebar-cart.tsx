import { Button } from '@/components/ui/button';
import {
  Trash2,
  Plus,
  Minus,
  CreditCard,
  Package,
  X,
} from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { Separator } from '@/components/ui/separator';

export interface SidebarCartItem {
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

export interface SidebarCartProps {
  isOpen: boolean;
  onClose: () => void;
  items: SidebarCartItem[];
  totalItems: number;
  onQuantityChange: (id: string, quantity: number) => void;
  onRemove: (id: string) => void;
  title: string;
  emptyText: string;
  /** Replaces the demo's free-shipping progress (no delivery rates are stated). */
  deliveryNote: string;
  subtotal: string;
  deliveryCost: string;
  total: string;
  /** Small line under the total. */
  totalNote?: string;
  checkoutLabel: string;
  continueLabel: string;
  onCheckout: () => void;
}

export default function SidebarCart({
  isOpen,
  onClose,
  items,
  totalItems,
  onQuantityChange,
  onRemove,
  title,
  emptyText,
  deliveryNote,
  subtotal,
  deliveryCost,
  total,
  totalNote,
  checkoutLabel,
  continueLabel,
  onCheckout,
}: SidebarCartProps) {
  // Escape closes the drawer.
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  return (
    <>
      {/* The demo's fixed-height wrapper and floating toggle button are dropped:
          the navbar's bag button opens this drawer. */}
      <div className="relative">
        {/* Sidebar Cart */}
        <div
          role="dialog"
          aria-modal="false"
          aria-label={title}
          aria-hidden={!isOpen}
          inert={!isOpen}
          className={`bg-background fixed top-0 right-0 z-40 h-full w-80 transform border-l shadow-xl transition-transform duration-300 md:w-96 ${
            isOpen ? 'translate-x-0' : 'translate-x-full'
          }`}
          style={{
            paddingTop: 'env(safe-area-inset-top, 0px)',
            paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          }}
        >
          <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b p-4">
              <div>
                <h2 className="text-lg font-semibold">{title}</h2>
                <p className="text-muted-foreground text-sm">
                  {totalItems} {totalItems === 1 ? 'item' : 'items'}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                aria-label="Close bag"
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            {/* Free Shipping Progress */}
            <div className="bg-muted/30 px-4 py-3">
              <div className="text-primary flex items-center gap-2 text-sm">
                <Package className="h-4 w-4" />
                <span>{deliveryNote}</span>
              </div>
            </div>

            {/* Cart Items */}
            <div className="flex-1 space-y-4 overflow-y-auto p-4">
              {items.length === 0 && (
                <p className="text-muted-foreground text-sm">{emptyText}</p>
              )}
              {items.map((item) => (
                <div
                  key={item.id}
                  className="flex gap-3 border-b pb-4 last:border-0"
                >
                  {/* Product Image */}
                  <div className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-md">
                    {item.image}
                  </div>

                  {/* Product Details */}
                  <div className="min-w-0 flex-1">
                    <div className="flex justify-between">
                      <div>
                        <h3 className="truncate pr-6 text-sm font-medium">
                          {item.name}
                        </h3>
                        <p className="text-muted-foreground text-xs">
                          {item.detail}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
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
                        <span className="w-7 text-center text-sm">
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
              ))}
            </div>

            {/* Order Summary */}
            <div className="space-y-4 border-t p-4">
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Subtotal</span>
                  <span>{subtotal}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>Delivery</span>
                  <span>{deliveryCost}</span>
                </div>
                <Separator />
                <div className="flex justify-between text-lg font-medium">
                  <span>Total</span>
                  <span>{total}</span>
                </div>
                {totalNote && <p className="text-muted-foreground text-xs">{totalNote}</p>}
              </div>

              <div className="space-y-2">
                <Button className="w-full" onClick={onCheckout}>
                  <CreditCard className="mr-2 h-4 w-4" />
                  {checkoutLabel}
                </Button>
                <Button variant="outline" className="w-full" onClick={onClose}>
                  {continueLabel}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
