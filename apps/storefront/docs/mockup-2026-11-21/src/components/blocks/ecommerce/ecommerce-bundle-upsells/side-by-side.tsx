import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

// Prices are display strings. The installed bundle discount, struck-through prices,
// "Save" badges and the bundle total are removed: there is no bundle offer.
interface AddOn {
  id: string;
  name: string;
  price: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  description: string;
}

export interface UpsellBundleProps {
  title: string;
  description: string;
  addOnsTitle: string;
  summaryTitle: string;
  mainProduct: {
    name: string;
    price: string;
    photo?: { src: string; alt: string; position?: string };
    placeholder: string;
    description: string;
  };
  addOns: AddOn[];
  /** Opens a piece's page (no bundle purchase). */
  cta: { label: string; to: Route };
}

export default function UpsellBundleSideBySide({
  title,
  description,
  addOnsTitle,
  summaryTitle,
  mainProduct,
  addOns,
  cta,
}: UpsellBundleProps) {
  const [selectedAddOns, setSelectedAddOns] = useState<string[]>([]);

  const handleAddOnToggle = (addOnId: string) => {
    setSelectedAddOns((prev) =>
      prev.includes(addOnId)
        ? prev.filter((id) => id !== addOnId)
        : [...prev, addOnId]
    );
  };

  const selectedAddOnItems = addOns.filter((addOn) =>
    selectedAddOns.includes(addOn.id)
  );

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 md:py-12">
      <div className="space-y-2 px-2 text-center">
        <h2 className="text-xl font-bold sm:text-2xl">{title}</h2>
        <p className="text-muted-foreground text-sm">
          {description}
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Main Product */}
        <Card className="h-fit">
          <CardContent className="p-4 sm:p-6">
            <div className="space-y-4">
              <div className="bg-muted relative aspect-square overflow-hidden rounded-lg">
                <ImageSlot
                  photo={mainProduct.photo}
                  placeholder={mainProduct.placeholder}
                  className="object-cover"
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-semibold sm:text-xl">
                  {mainProduct.name}
                </h3>
                <p className="text-muted-foreground text-xs sm:text-sm">
                  {mainProduct.description}
                </p>
                <div className="text-xl font-bold sm:text-2xl">
                  {mainProduct.price}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Add-ons */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">{addOnsTitle}</h3>
          <div className="space-y-3">
            {addOns.map((addOn) => (
              <Card
                key={addOn.id}
                className="hover:bg-muted/50 transition-colors"
              >
                <CardContent className="p-3 sm:p-4">
                  <div className="flex items-start space-x-2 sm:space-x-4">
                    <Checkbox
                      id={addOn.id}
                      checked={selectedAddOns.includes(addOn.id)}
                      onCheckedChange={() => handleAddOnToggle(addOn.id)}
                      className="mt-1 h-5 w-5"
                    />
                    <div className="flex-shrink-0">
                      <div className="bg-muted relative h-12 w-12 overflow-hidden rounded-md sm:h-16 sm:w-16">
                        <ImageSlot
                          photo={addOn.photo}
                          placeholder={addOn.placeholder}
                          className="object-cover"
                        />
                      </div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <label
                        htmlFor={addOn.id}
                        className="block cursor-pointer text-sm font-medium sm:text-base"
                      >
                        {addOn.name}
                      </label>
                      <p className="text-muted-foreground mt-1 text-xs sm:text-sm">
                        {addOn.description}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="font-semibold">
                          {addOn.price}
                        </span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>

      {/* Bundle Summary */}
      <Card className="border-2">
        <CardContent className="p-4 sm:p-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">{summaryTitle}</h3>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="pr-2">{mainProduct.name}</span>
                <span>{mainProduct.price}</span>
              </div>
              {selectedAddOnItems.map((addOn) => (
                <div
                  key={addOn.id}
                  className="text-muted-foreground flex justify-between"
                >
                  <span className="pr-2">{addOn.name}</span>
                  <span>{addOn.price}</span>
                </div>
              ))}
            </div>

            <div className="border-t pt-4">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  size="lg"
                  className="w-full sm:ml-auto sm:w-auto sm:min-w-[140px]"
                  asChild
                >
                  <Link to={cta.to}>{cta.label}</Link>
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
