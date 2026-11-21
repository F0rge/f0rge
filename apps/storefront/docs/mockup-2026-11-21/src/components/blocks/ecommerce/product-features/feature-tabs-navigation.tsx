import { useState } from 'react';

import { ArrowRight, type LucideIcon } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ImageSlot } from '@/components/photo';
import { Link, type Route } from '@/lib/router';

export interface FeatureTab {
  id: string;
  label: string;
  /** Tab icon (lucide). */
  icon: LucideIcon;
  title: string;
  description: string;
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  link: { label: string; to: Route };
  /** Feature cards for the tab, each with its own icon. */
  features: { title: string; description: string; icon: LucideIcon }[];
}

export interface FeatureTabsNavigationProps {
  badge: string;
  title: string;
  description: string;
  tabs: FeatureTab[];
  specsTitle: string;
  /** Four spec cards: label, value, optional note. */
  specs: { label: string; value: string; note?: string }[];
  primary: { label: string; to: Route };
  secondary: { label: string; to: Route };
}

export default function FeatureTabsNavigation({
  badge,
  title,
  description,
  tabs,
  specsTitle,
  specs,
  primary,
  secondary,
}: FeatureTabsNavigationProps) {
  const [activeTab, setActiveTab] = useState(tabs[0]?.id ?? '');

  const featureCategories = tabs.map((tab) => {
    const TabIcon = tab.icon;
    return {
      ...tab,
      icon: <TabIcon className="mr-2 h-4 w-4" />,
      features: tab.features.map((feature) => {
        const FeatureIcon = feature.icon;
        return { ...feature, icon: <FeatureIcon className="h-5 w-5" /> };
      }),
    };
  });

  // Find the active category
  const activeCategory =
    featureCategories.find((cat) => cat.id === activeTab) ||
    featureCategories[0]!;

  return (
    <section className="bg-background w-full py-12 md:py-24 lg:py-32">
      <div className="container mx-auto px-4 md:px-6 2xl:max-w-[1400px]">
        <div className="mb-8 flex flex-col items-center space-y-4 text-center">
          <Badge variant="outline" className="px-3.5 py-1.5">
            {badge}
          </Badge>
          <h2 className="text-3xl font-bold tracking-tighter sm:text-4xl md:text-5xl">
            {title}
          </h2>
          <p className="text-muted-foreground max-w-[800px] md:text-xl/relaxed lg:text-center">
            {description}
          </p>
        </div>

        <Tabs
          defaultValue={tabs[0]?.id}
          value={activeTab}
          onValueChange={setActiveTab}
          className="mb-8 w-full"
        >
          <div className="mb-8 flex justify-center">
            {/* ui/tabs pins the list to group-data-horizontal/tabs:h-9 and triggers to
                h-[calc(100%-1px)] (newer shadcn Tabs); h-auto on both lets the track grow
                around the py-3 triggers, with p-1/gap-1 visible on every side. */}
            <TabsList className="grid h-auto w-full max-w-3xl grid-cols-2 gap-1 p-1 group-data-horizontal/tabs:h-auto md:grid-cols-4">
              {featureCategories.map((category) => (
                <TabsTrigger
                  key={category.id}
                  value={category.id}
                  className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-active:bg-primary data-active:text-primary-foreground flex h-auto items-center justify-center py-3"
                >
                  {category.icon}
                  {category.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </div>

          {/* Main product image */}
          <div className="mb-12 overflow-hidden rounded-xl border">
            <ImageSlot
              photo={activeCategory.photo}
              placeholder={activeCategory.placeholder}
              className="h-[300px] w-full object-cover transition-all duration-500 md:h-[500px]"
            />
          </div>

          {featureCategories.map((category) => (
            <TabsContent
              key={category.id}
              value={category.id}
              className="data-[state=active]:animate-in data-[state=active]:fade-in-50 mt-0"
            >
              <div className="mb-12 grid items-center gap-12 md:grid-cols-2">
                <div className="space-y-4">
                  <h3 className="text-2xl font-bold">{category.title}</h3>
                  <p className="text-muted-foreground">
                    {category.description}
                  </p>
                  <Button asChild>
                    <Link to={category.link.to}>
                      {category.link.label}
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </div>

                <div className="space-y-6">
                  {category.features.map((feature, idx) => (
                    <div
                      key={idx}
                      className="bg-muted/40 flex items-start gap-4 rounded-lg border p-4"
                    >
                      <div className="bg-primary/10 text-primary mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
                        {feature.icon}
                      </div>
                      <div>
                        <h4 className="text-base font-medium">
                          {feature.title}
                        </h4>
                        <p className="text-muted-foreground mt-1 text-sm">
                          {feature.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>
          ))}
        </Tabs>

        {/* Specs section */}
        <div className="mt-12 border-t pt-12">
          <h3 className="mb-8 text-center text-xl font-semibold">
            {specsTitle}
          </h3>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
            {specs.map((spec) => (
              <div key={spec.label} className="space-y-2 rounded-lg border p-4 text-center">
                <h4 className="text-muted-foreground text-sm font-medium tracking-wide uppercase">
                  {spec.label}
                </h4>
                <p className="font-medium">{spec.value}</p>
                {spec.note && <p className="text-muted-foreground text-sm">{spec.note}</p>}
              </div>
            ))}
          </div>
        </div>

        {/* CTA section */}
        <div className="mt-12 flex flex-col items-center justify-center space-y-4 text-center">
          <div className="flex flex-col gap-4 sm:flex-row">
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
    </section>
  );
}
