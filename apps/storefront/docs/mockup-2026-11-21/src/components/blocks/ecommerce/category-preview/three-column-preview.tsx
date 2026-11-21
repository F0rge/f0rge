import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface Category {
  name: string;
  description: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  /** Shown where the demo had "48 products". */
  countLabel: string;
  to: Route;
}

export interface ThreeColumnPreviewProps {
  categories: Category[];
  ctaLabel: string;
}

export default function ThreeColumnPreview({ categories, ctaLabel }: ThreeColumnPreviewProps) {
  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3">
        {categories.map((category) => (
          <div
            key={category.name}
            className="group bg-card relative overflow-hidden rounded-xl border"
          >
            {/* Image */}
            <div className="bg-muted relative aspect-[4/3]">
              <ImageSlot
                photo={category.photo}
                placeholder={category.placeholder}
                className="object-cover transition-transform duration-500 group-hover:scale-105"
              />
              <div className="from-background/80 to-background/0 absolute inset-0 bg-gradient-to-t" />
            </div>

            {/* Content */}
            <div className="absolute inset-0 flex flex-col justify-end p-6">
              <h3 className="mb-2 text-xl font-semibold tracking-tight">
                {category.name}
              </h3>
              <p className="text-accent-foreground/80 mb-4 text-sm">
                {category.description}
              </p>
              <div className="flex items-center justify-between">
                <span className="text-accent-foreground/80 text-sm">
                  {category.countLabel}
                </span>
                <Button
                  variant="ghost"
                  className="-translate-x-2 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100 focus-visible:translate-x-0 focus-visible:opacity-100"
                  asChild
                >
                  <Link to={category.to}>
                    {ctaLabel}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>

            {/* Hover Overlay */}
            <div className="bg-primary/5 pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
          </div>
        ))}
      </div>
    </div>
  );
}
