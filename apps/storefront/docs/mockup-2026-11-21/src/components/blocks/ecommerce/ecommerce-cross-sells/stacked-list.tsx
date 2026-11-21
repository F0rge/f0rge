import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import type { ReactNode } from 'react';
import { Link, type Route } from '@/lib/router';

export interface CrossSellStackedItem {
  id: string;
  title: string;
  /** Display text (placeholders allowed). */
  price: string;
  image: ReactNode;
  action: { label: string; to: Route };
}

export interface CrossSellStackedListProps {
  title: string;
  products: CrossSellStackedItem[];
}

export default function CrossSellStackedList({ title, products }: CrossSellStackedListProps) {
  return (
    <div className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-md">
        <h3 className="text-foreground mb-4 text-lg font-semibold">{title}</h3>

        <div className="space-y-3">
          {products.map((product) => (
            <Card key={product.id} className="p-3">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">{product.image}</div>

                <div className="min-w-0 flex-1">
                  <h4 className="text-foreground truncate text-sm font-medium">
                    {product.title}
                  </h4>
                  <p className="text-foreground mt-1 text-sm font-semibold">
                    {product.price}
                  </p>
                </div>

                <div className="flex-shrink-0">
                  <Button size="sm" className="h-8 px-3 text-xs" asChild>
                    <Link to={product.action.to}>{product.action.label}</Link>
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
