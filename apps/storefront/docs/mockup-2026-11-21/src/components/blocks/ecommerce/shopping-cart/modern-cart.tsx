import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Trash2,
  Plus,
  Minus,
  Package,
  CreditCard,
  Truck,
  Shield,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { Link, type Route } from '@/lib/router';

export interface ModernCartItem {
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

export interface ModernCartProps {
  items: ModernCartItem[];
  totalItems: number;
  onQuantityChange: (id: string, quantity: number) => void;
  onRemove: (id: string) => void;
  title: string;
  emptyText: string;
  emptyAction: { label: string; to: Route };
  summaryTitle: string;
  summaryDescription: string;
  /** Replaces the demo's shipping-method select (no delivery rates are stated). */
  deliveryLabel: string;
  deliveryNote: string;
  subtotal: string;
  deliveryCost: string;
  total: string;
  /** Small line under the total. */
  totalNote?: string;
  /** Three short lines; replaces the demo's returns/payment/delivery claims. */
  features: [string, string, string];
  checkout: { label: string; to: Route };
}

export default function ModernCart({
  items,
  totalItems,
  onQuantityChange,
  onRemove,
  title,
  emptyText,
  emptyAction,
  summaryTitle,
  summaryDescription,
  deliveryLabel,
  deliveryNote,
  subtotal,
  deliveryCost,
  total,
  totalNote,
  features,
  checkout,
}: ModernCartProps) {
  const empty = items.length === 0;

  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Main Cart Section */}
        <div className="space-y-6 lg:col-span-2">
          <div>
            <h1 className="text-2xl font-semibold">{title}</h1>
            <p className="text-muted-foreground">
              {totalItems} {totalItems === 1 ? 'item' : 'items'} in your bag
            </p>
          </div>

          <div className="space-y-4">
            {empty && (
              <Card>
                <CardContent className="space-y-4">
                  <p className="text-muted-foreground">{emptyText}</p>
                  <Button variant="outline" asChild>
                    <Link to={emptyAction.to}>{emptyAction.label}</Link>
                  </Button>
                </CardContent>
              </Card>
            )}
            {items.map((item) => (
              <Card key={item.id} className="overflow-hidden p-0">
                <CardContent className="p-0">
                  <div className="flex h-full flex-col md:flex-row">
                    {/* Product Image */}
                    <div className="relative h-auto w-full md:w-32">
                      {item.image}
                    </div>

                    {/* Product Details */}
                    <div className="flex-1 p-6 pb-3">
                      <div className="flex justify-between">
                        <div>
                          <h3 className="font-medium">{item.name}</h3>
                          <p className="text-muted-foreground text-sm">
                            {item.detail}
                          </p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => onRemove(item.id)}
                          aria-label={`Remove ${item.name}, ${item.detail}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="mt-4 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() =>
                              onQuantityChange(item.id, Math.max(1, item.quantity - 1))
                            }
                            aria-label="Decrease quantity"
                          >
                            <Minus className="h-4 w-4" />
                          </Button>
                          <span className="w-8 text-center" aria-live="polite">
                            {item.quantity}
                          </span>
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => onQuantityChange(item.id, item.quantity + 1)}
                            disabled={item.max !== undefined && item.quantity >= item.max}
                            aria-label="Increase quantity"
                          >
                            <Plus className="h-4 w-4" />
                          </Button>
                        </div>

                        <div className="text-right">
                          <div className="font-medium">{item.price}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Order Summary */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{summaryTitle}</CardTitle>
              <CardDescription>{summaryDescription}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Delivery (the demo's shipping-method select and promo code are dropped) */}
              <div className="space-y-2">
                <Label>{deliveryLabel}</Label>
                <p className="text-muted-foreground text-sm">{deliveryNote}</p>
              </div>

              {/* Order Summary */}
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

              {/* Features */}
              <div className="space-y-4 border-t pt-4">
                <div className="flex items-center gap-2 text-sm">
                  <Package className="text-primary h-4 w-4" />
                  <span>{features[0]}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Shield className="text-primary h-4 w-4" />
                  <span>{features[1]}</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Truck className="text-primary h-4 w-4" />
                  <span>{features[2]}</span>
                </div>
              </div>

              {/* Checkout Button */}
              {empty ? (
                <Button className="w-full" disabled>
                  <CreditCard className="mr-2 h-4 w-4" />
                  {checkout.label}
                </Button>
              ) : (
                <Button className="w-full" asChild>
                  <Link to={checkout.to}>
                    <CreditCard className="mr-2 h-4 w-4" />
                    {checkout.label}
                  </Link>
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
