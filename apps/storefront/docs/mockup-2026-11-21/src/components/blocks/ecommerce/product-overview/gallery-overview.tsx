import { Button } from '@/components/ui/button';
import { ZoomIn } from 'lucide-react';
import { ImageSlot } from '@/components/photo';

export interface GalleryImage {
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
}

export interface GalleryOverviewProps<O extends string> {
  eyebrow: string;
  name: string;
  price: string;
  /** Small line under the price, e.g. "incl. VAT · SKU 60244 · 2 in stock". */
  priceNote?: string;
  description: string;
  /** Bullet list under the description; omitted when empty. */
  points: string[];
  /** Main image, then up to four masonry slots in order. Masonry slots without an
   *  image are not rendered: with two, only the block's first 8/4 row shows. */
  images: [GalleryImage, ...GalleryImage[]];
  /** The block's "Size" option row (here: quantity, up to stock). */
  option?: { label: string; values: O[]; selected: O; onSelect: (value: O) => void };
  primary: { label: string; onClick: () => void };
  secondary?: { label: string; onClick: () => void };
  assurances: { title: string; description: string }[];
}

export default function GalleryOverview<O extends string>({
  eyebrow,
  name,
  price,
  priceNote,
  description,
  points,
  images,
  option,
  primary,
  secondary,
  assurances,
}: GalleryOverviewProps<O>) {
  const [main, detail, side, closeUp, lifestyle] = images;
  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
        {/* Gallery Section */}
        <div className="space-y-4">
          {/* Main Image */}
          <div className="bg-muted group relative aspect-square overflow-hidden rounded-xl">
            <ImageSlot
              photo={main.photo}
              placeholder={main.placeholder}
              className="object-cover transition-transform duration-300 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-black/0 transition-colors duration-300 group-hover:bg-black/20">
              <Button
                size="icon"
                variant="outline"
                className="bg-background/80 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0 backdrop-blur-sm transition-opacity duration-300 group-hover:opacity-100"
                aria-label="Zoom"
              >
                <ZoomIn className="h-5 w-5" />
              </Button>
            </div>
          </div>

          {/* Masonry Gallery */}
          {detail && (
          <div className="grid grid-cols-12 gap-4">
            {detail && (
            <div className="bg-muted group relative col-span-8 aspect-[4/3] overflow-hidden rounded-xl">
              <ImageSlot
                photo={detail.photo}
                placeholder={detail.placeholder}
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
            )}
            {side && (
            <div className="bg-muted group relative col-span-4 aspect-[3/4] overflow-hidden rounded-xl">
              <ImageSlot
                photo={side.photo}
                placeholder={side.placeholder}
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
            )}
            {closeUp && (
            <div className="bg-muted group relative col-span-4 aspect-square overflow-hidden rounded-xl">
              <ImageSlot
                photo={closeUp.photo}
                placeholder={closeUp.placeholder}
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
            )}
            {lifestyle && (
            <div className="bg-muted group relative col-span-8 aspect-video overflow-hidden rounded-xl">
              <ImageSlot
                photo={lifestyle.photo}
                placeholder={lifestyle.placeholder}
                className="object-cover transition-transform duration-300 group-hover:scale-105"
              />
            </div>
            )}
          </div>
          )}
        </div>

        {/* Product Info */}
        <div className="space-y-8 lg:sticky lg:top-20">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <span className="text-primary text-sm font-medium">
                {eyebrow}
              </span>
              <h1 className="text-3xl font-bold">{name}</h1>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-baseline gap-4">
              <span className="text-3xl font-bold">{price}</span>
            </div>
            {priceNote && (
              <p className="text-muted-foreground text-sm">{priceNote}</p>
            )}
          </div>

          <div className="prose dark:prose-invert">
            <p>
              {description}
            </p>
            {points.length > 0 && (
            <ul className="mt-3 list-disc space-y-1 pl-5">
              {points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
            )}
          </div>

          {option && (
          <div className="space-y-6 border-t pt-6">
            <div className="space-y-2">
              <label className="mb-2 text-sm font-medium">{option.label}</label>
              <div className="grid grid-cols-3 gap-3">
                {option.values.map((value) => (
                  <Button
                    key={value}
                    variant={value === option.selected ? 'default' : 'outline'}
                    className="h-12"
                    aria-pressed={value === option.selected}
                    onClick={() => option.onSelect(value)}
                  >
                    {value}
                  </Button>
                ))}
              </div>
            </div>
          </div>
          )}

          <div className="flex gap-4">
            <Button size="lg" className="flex-1" onClick={primary.onClick}>
              {primary.label}
            </Button>
            {secondary && (
              <Button size="lg" variant="outline" className="flex-1" onClick={secondary.onClick}>
                {secondary.label}
              </Button>
            )}
          </div>

          <div className="border-t pt-6">
            <div className="grid grid-cols-3 gap-4 text-center text-sm">
              {assurances.map((item) => (
                <div key={item.title} className="space-y-1">
                  <span className="block font-medium">{item.title}</span>
                  <span className="text-muted-foreground block">
                    {item.description}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
