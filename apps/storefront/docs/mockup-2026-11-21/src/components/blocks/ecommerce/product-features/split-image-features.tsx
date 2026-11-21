import { Button } from '@/components/ui/button';
import { ChevronRight, ArrowRight } from 'lucide-react';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface SplitImage {
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
}

export interface SplitImageFeaturesProps {
  badge: string;
  title: string;
  description: string;
  /** Four slots: left column top/bottom, right column top/bottom. */
  images: [SplitImage, SplitImage, SplitImage, SplitImage];
  features: { title: string; description: string }[];
  divider: string;
  primary: { label: string; to: Route };
  secondary: { label: string; to: Route };
}

export default function SplitImageFeatures({
  badge,
  title,
  description,
  images,
  features,
  divider,
  primary,
  secondary,
}: SplitImageFeaturesProps) {
  return (
    <section className="bg-background w-full py-12 md:py-24 lg:py-32">
      <div className="container mx-auto px-4 md:px-6 2xl:max-w-[1400px]">
        <div className="grid items-center gap-6 lg:grid-cols-2 lg:gap-12">
          {/* Left side - Images */}
          <div className="relative">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-4">
                <div className="overflow-hidden rounded-lg">
                  <ImageSlot
                    photo={images[0].photo}
                    placeholder={images[0].placeholder}
                    className="aspect-[4/5] h-auto w-full object-cover"
                  />
                </div>
                <div className="overflow-hidden rounded-lg">
                  <ImageSlot
                    photo={images[1].photo}
                    placeholder={images[1].placeholder}
                    className="aspect-[4/3] h-auto w-full object-cover"
                  />
                </div>
              </div>
              <div className="mt-8 space-y-4">
                <div className="overflow-hidden rounded-lg">
                  <ImageSlot
                    photo={images[2].photo}
                    placeholder={images[2].placeholder}
                    className="aspect-[4/3] h-auto w-full object-cover"
                  />
                </div>
                <div className="overflow-hidden rounded-lg">
                  <ImageSlot
                    photo={images[3].photo}
                    placeholder={images[3].placeholder}
                    className="aspect-[4/5] h-auto w-full object-cover"
                  />
                </div>
              </div>
            </div>

            {/* Design elements */}
            <div className="bg-primary/10 absolute -bottom-4 -left-4 -z-10 h-24 w-24 rounded-full blur-xl"></div>
            <div className="bg-primary/10 absolute -top-4 -right-4 -z-10 h-24 w-24 rounded-full blur-xl"></div>
          </div>

          {/* Right side - Content */}
          <div className="flex flex-col space-y-8">
            <div className="space-y-2">
              <div className="bg-primary/10 text-primary inline-block rounded-full px-3 py-1 text-sm">
                {badge}
              </div>
              <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">
                {title}
              </h2>
              <p className="text-muted-foreground max-w-[600px] md:text-xl/relaxed">
                {description}
              </p>
            </div>

            <div className="space-y-4">
              {features.map((feature, index) => (
                <div
                  key={index}
                  className="bg-card text-card-foreground hover:bg-muted/50 flex rounded-lg border p-4 transition-colors"
                >
                  <div className="bg-primary/10 text-primary mr-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-full">
                    <ChevronRight className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="font-medium">{feature.title}</h3>
                    <p className="text-muted-foreground text-sm">
                      {feature.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="bg-border h-px flex-1"></div>
                <span className="text-muted-foreground text-sm">
                  {divider}
                </span>
                <div className="bg-border h-px flex-1"></div>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button size="lg" asChild>
                  <Link to={primary.to}>
                    {primary.label}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link to={secondary.to}>{secondary.label}</Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
