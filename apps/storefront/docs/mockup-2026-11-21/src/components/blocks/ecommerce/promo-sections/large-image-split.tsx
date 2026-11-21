import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Check } from 'lucide-react';
import { Link, type Route } from '@/lib/router';
import { ImageSlot } from '@/components/photo';

export interface LargeImageSplitPromoProps {
  badge: string;
  title: string;
  description: string;
  /** Check-mark list; omitted when empty. */
  points?: string[];
  primary: { label: string; to: Route };
  secondary: { label: string; to: Route };
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
}

export default function LargeImageSplitPromo({
  badge,
  title,
  description,
  points = [],
  primary,
  secondary,
  photo,
  placeholder,
}: LargeImageSplitPromoProps) {
  return (
    <div className="bg-background relative overflow-hidden">
      <div className="mx-auto max-w-7xl lg:grid lg:grid-cols-12 lg:gap-x-8 lg:px-8">
        {/* Content Section */}
        <div className="px-6 pt-10 pb-24 sm:pb-32 lg:col-span-7 lg:px-0 lg:pt-48 lg:pb-56 xl:col-span-6">
          <div className="mx-auto max-w-2xl lg:mx-0">
            <Badge variant="secondary" className="mb-4">
              {badge}
            </Badge>
            <h1 className="text-foreground mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
              {title}
            </h1>
            <p className="text-muted-foreground mt-6 text-lg leading-8">
              {description}
            </p>
            {points.length > 0 && (
            <ul
              role="list"
              className="text-muted-foreground mt-8 space-y-3 text-sm leading-6"
            >
              {points.map((point) => (
                <li key={point} className="flex items-center gap-x-3">
                  <Check
                    className="text-primary h-5 w-5 flex-none"
                    aria-hidden="true"
                  />
                  {point}
                </li>
              ))}
            </ul>
            )}
            <div className="mt-10 flex items-center gap-x-6">
              <Button size="lg" asChild>
                <Link to={primary.to}>{primary.label}</Link>
              </Button>
              <Button variant="outline" size="lg" asChild>
                <Link to={secondary.to}>{secondary.label}</Link>
              </Button>
            </div>
          </div>
        </div>

        {/* Image Section */}
        <div className="relative lg:col-span-5 lg:-mr-8 xl:absolute xl:inset-y-0 xl:right-0 xl:w-1/2">
          <ImageSlot
            photo={photo}
            placeholder={placeholder}
            className='bg-muted aspect-[3/2] w-full object-cover lg:absolute lg:inset-0 lg:aspect-auto lg:h-full'
          />
        </div>
      </div>
    </div>
  );
}
