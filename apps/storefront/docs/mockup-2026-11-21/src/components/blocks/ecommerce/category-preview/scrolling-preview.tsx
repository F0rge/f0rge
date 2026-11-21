import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ArrowRight, ArrowLeft } from 'lucide-react';
import { useRef } from 'react';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface ScrollingPreviewCategory {
  name: string;
  description: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  /** Replaces the demo's product count, e.g. "4 pieces". */
  countLabel: string;
  to: Route;
  /** The demo's "Featured Brands" chips; omitted when there is nothing true to list. */
  featured?: string[];
}

export interface ScrollingPreviewProps {
  title: string;
  description: string;
  ctaLabel: string;
  categories: ScrollingPreviewCategory[];
}

export default function ScrollingPreview({ title, description, ctaLabel, categories }: ScrollingPreviewProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const container = scrollContainerRef.current;
      const scrollAmount =
        direction === 'left' ? -container.clientWidth : container.clientWidth;
      container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <div className="mx-auto w-full max-w-7xl p-6">
      {/* Navigation */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">
            {title}
          </h2>
          <p className="text-muted-foreground mt-1">
            {description}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => scroll('left')} aria-label="Scroll left">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={() => scroll('right')} aria-label="Scroll right">
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Scrolling Cards */}
      <div
        ref={scrollContainerRef}
        className="scrollbar-none flex snap-x snap-mandatory gap-6 overflow-x-auto pb-4"
      >
        {categories.map((category) => (
          <Card
            key={category.name}
            className="group w-[calc(100%-2rem)] flex-none snap-start p-0 transition-shadow duration-300 hover:shadow-lg sm:w-[calc(50%-1rem)] lg:w-[calc(33.333%-1rem)]"
          >
            <CardContent className="p-0">
              {/* Image */}
              <div className="relative aspect-[16/9]">
                <ImageSlot
                  photo={category.photo}
                  placeholder={category.placeholder}
                  className="rounded-t-xl object-cover"
                />
                <div className="from-background/80 to-background/0 absolute inset-0 rounded-t-xl bg-gradient-to-t" />
              </div>

              {/* Content */}
              <div className="p-6">
                <h3 className="mb-2 text-xl font-semibold tracking-tight">
                  {category.name}
                </h3>
                <p className="text-muted-foreground mb-4 text-sm">
                  {category.description}
                </p>

                {/* Featured Brands */}
                {category.featured && (
                  <div className="mb-4">
                    <div className="mb-2 text-sm font-medium">
                      Featured Brands:
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {category.featured.map((brand) => (
                        <div
                          key={brand}
                          className="bg-primary/10 text-primary rounded-md px-2 py-1 text-xs"
                        >
                          {brand}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground text-sm">
                    {category.countLabel}
                  </span>
                  <Button
                    variant="ghost"
                    asChild
                    className="-translate-x-2 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100 focus-visible:translate-x-0 focus-visible:opacity-100"
                  >
                    <Link to={category.to}>
                      {ctaLabel}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
