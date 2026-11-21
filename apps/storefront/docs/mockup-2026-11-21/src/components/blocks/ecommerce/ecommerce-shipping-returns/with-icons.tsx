import { Truck, RotateCcw } from "lucide-react";

export interface ShippingReturnsWithIconsProps {
  shipping: { title: string; body: string };
  returns: { title: string; body: string };
}

export default function ShippingReturnsWithIcons({ shipping, returns }: ShippingReturnsWithIconsProps) {
  return (
    <div className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-4xl">
        <div className="grid gap-8 md:grid-cols-2 md:gap-12">
          {/* Shipping Section */}
          <div className="flex flex-col items-center text-center md:items-start md:text-left">
            <div className="bg-primary/10 mb-4 flex h-12 w-12 items-center justify-center rounded-lg">
              <Truck className="text-primary h-6 w-6" />
            </div>
            <h3 className="text-foreground mb-3 text-lg font-semibold">
              {shipping.title}
            </h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              {shipping.body}
            </p>
          </div>

          {/* Returns Section */}
          <div className="flex flex-col items-center text-center md:items-start md:text-left">
            <div className="bg-primary/10 mb-4 flex h-12 w-12 items-center justify-center rounded-lg">
              <RotateCcw className="text-primary h-6 w-6" />
            </div>
            <h3 className="text-foreground mb-3 text-lg font-semibold">
              {returns.title}
            </h3>
            <p className="text-muted-foreground text-sm leading-relaxed">
              {returns.body}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
