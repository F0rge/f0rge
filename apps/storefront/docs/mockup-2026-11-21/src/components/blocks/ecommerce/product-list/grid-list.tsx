import { Button } from '@/components/ui/button';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

/** A card button: a link (`to`), an action (`onClick`), or disabled when it has neither. */
export interface GridListAction {
  label: string;
  to?: Route;
  onClick?: () => void;
}

export interface GridListProduct {
  id: string;
  name: string;
  price: string;
  /** Replaces the demo's struck-through price line, e.g. "2 in stock" or "Made to order". */
  availabilityLabel: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  /** Two buttons, primary first. */
  actions: [GridListAction, GridListAction];
}

export interface GridListProps {
  products: GridListProduct[];
}

function ActionButton({
  action,
  ...props
}: { action: GridListAction } & React.ComponentProps<typeof Button>) {
  if (action.to) {
    return (
      <Button {...props} asChild>
        <Link to={action.to}>{action.label}</Link>
      </Button>
    );
  }
  return (
    <Button {...props} onClick={action.onClick} disabled={!action.onClick}>
      {action.label}
    </Button>
  );
}

export default function GridList({ products }: GridListProps) {
  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      {/* One column fewer than installed (lg:3 xl:4): the grid sits beside the filter sidebar. */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
        {/* Product Card */}
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
                  <h3 className="line-clamp-2 font-medium">
                    {product.name}
                  </h3>
                </div>
                <div className="text-right">
                  <div className="font-medium whitespace-nowrap">{product.price}</div>
                  <div className="text-muted-foreground text-sm">
                    {product.availabilityLabel}
                  </div>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <ActionButton size="sm" className="w-full" action={product.actions[0]} />
                <ActionButton size="sm" variant="outline" className="w-full" action={product.actions[1]} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
