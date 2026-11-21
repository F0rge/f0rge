import { Button } from '@/components/ui/button';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface FeaturedListAction {
  label: string;
  to?: Route;
  onClick?: () => void;
}

export interface FeaturedListProduct {
  id: string;
  name: string;
  description: string;
  price: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  /** Two buttons, primary first. */
  actions: [FeaturedListAction, FeaturedListAction];
}

export interface FeaturedListProps {
  featuredBadge: string;
  featured: FeaturedListProduct;
  products: FeaturedListProduct[];
}

function ActionButton({
  action,
  ...props
}: { action: FeaturedListAction } & React.ComponentProps<typeof Button>) {
  return action.to ? (
    <Button {...props} asChild>
      <Link to={action.to}>{action.label}</Link>
    </Button>
  ) : (
    <Button {...props} onClick={action.onClick}>
      {action.label}
    </Button>
  );
}

export default function FeaturedList({ featuredBadge, featured, products }: FeaturedListProps) {
  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Featured Product */}
        <div className="group bg-card overflow-hidden rounded-xl border md:col-span-2">
          <div className="grid md:grid-cols-2">
            <div className="bg-muted relative aspect-square md:aspect-auto">
              <ImageSlot
                photo={featured.photo}
                placeholder={featured.placeholder}
                className="object-cover transition-transform group-hover:scale-105"
              />
              <div className="bg-primary text-primary-foreground absolute top-2 left-2 rounded-md px-2 py-1 text-sm font-medium">
                {featuredBadge}
              </div>
            </div>
            <div className="flex flex-col p-6">
              <div className="flex-1">
                <h2 className="text-2xl font-semibold">{featured.name}</h2>
                <p className="text-muted-foreground mt-4">{featured.description}</p>
                <div className="mt-4 space-y-2">
                  <div className="flex items-baseline gap-2">
                    <span className="text-2xl font-bold">{featured.price}</span>
                  </div>
                </div>
              </div>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <ActionButton size="lg" action={featured.actions[0]} />
                <ActionButton size="lg" variant="outline" action={featured.actions[1]} />
              </div>
            </div>
          </div>
        </div>

        {/* Regular Products */}
        {products.map((product) => (
          <div
            key={product.id}
            className="group bg-card overflow-hidden rounded-xl border"
          >
            <div className="bg-muted relative aspect-square">
              <ImageSlot
                photo={product.photo}
                placeholder={product.placeholder}
                className="object-cover transition-transform group-hover:scale-105"
              />
            </div>
            <div className="p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <h3 className="truncate font-medium">{product.name}</h3>
                </div>
                <div className="text-right">
                  <div className="font-medium">{product.price}</div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <ActionButton size="sm" action={product.actions[0]} />
                <ActionButton size="sm" variant="outline" action={product.actions[1]} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
