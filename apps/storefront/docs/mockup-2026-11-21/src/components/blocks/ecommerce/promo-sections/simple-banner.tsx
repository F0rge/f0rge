import { Button } from '@/components/ui/button';
import { Link, type Route } from '@/lib/router';

export interface SimpleBannerPromoProps {
  title: string;
  subtitle: string;
  primary: { label: string; to: Route };
  secondary: { label: string; to: Route };
}

export default function SimpleBannerPromo({ title, subtitle, primary, secondary }: SimpleBannerPromoProps) {
  return (
    <div className="bg-primary">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:flex lg:items-center lg:justify-between lg:px-8 lg:py-16">
        <h2 className="text-primary-foreground text-3xl font-bold tracking-tight sm:text-4xl">
          <span className="block">{title}</span>
          <span className="text-primary-foreground/80 block">
            {subtitle}
          </span>
        </h2>
        <div className="mt-8 flex lg:mt-0 lg:ml-4 lg:flex-shrink-0">
          <Button size="lg" variant="secondary" asChild>
            <Link to={primary.to}>{primary.label}</Link>
          </Button>
          <Button
            size="lg"
            variant="ghost"
            asChild
            className="text-primary-foreground hover:bg-primary/80 hover:text-primary-foreground ml-3"
          >
            <Link to={secondary.to}>{secondary.label}</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
