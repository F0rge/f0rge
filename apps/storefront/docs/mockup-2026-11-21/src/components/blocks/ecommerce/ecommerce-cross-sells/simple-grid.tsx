import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface CrossSellProduct {
  id: string;
  name: string;
  description: string;
  price: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  to: Route;
}

export interface CrossSellSimpleGridProps {
  title: string;
  ctaLabel: string;
  products: CrossSellProduct[];
}

export default function CrossSellSimpleGrid({ title, ctaLabel, products }: CrossSellSimpleGridProps) {
  const relatedProducts = products;
  return (
    <section className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-6xl">
        <h2 className="mb-8 text-center text-2xl font-bold tracking-tight">
          {title}
        </h2>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {relatedProducts.map((product) => (
            <Card
              key={product.id}
              className="group overflow-hidden border-0 p-0 shadow-sm transition-shadow hover:shadow-md"
            >
              <CardContent className="p-0">
                <div className="relative overflow-hidden">
                  <Link to={product.to} className="block" tabIndex={-1} aria-hidden>
                    <ImageSlot
                      photo={product.photo}
                      placeholder={product.placeholder}
                      className="h-48 w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    />
                  </Link>
                </div>

                <div className="space-y-3 p-4">
                  <div className="space-y-1">
                    <Link to={product.to} className="block">
                      <h3 className="hover:text-primary line-clamp-2 text-sm leading-tight font-semibold transition-colors">
                        {product.name}
                      </h3>
                    </Link>
                    <p className="text-muted-foreground line-clamp-2 text-xs">
                      {product.description}
                    </p>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold">{product.price}</span>
                    <Button size="sm" variant="outline" className="text-xs" asChild>
                      <Link to={product.to}>{ctaLabel}</Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
