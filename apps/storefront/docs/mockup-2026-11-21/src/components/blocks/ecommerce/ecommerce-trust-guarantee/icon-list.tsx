import type { LucideIcon } from "lucide-react";

export interface TrustIconListItem {
  icon: LucideIcon;
  title: string;
  description: string;
}

export default function TrustGuaranteeIconList({
  items: trustFeatures,
}: {
  items: TrustIconListItem[];
}) {
  return (
    <div className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-md">
        <div className="space-y-4">
          {trustFeatures.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div key={index} className="flex items-start gap-3">
                <div className="mt-0.5 flex-shrink-0">
                  <div className="bg-muted flex h-8 w-8 items-center justify-center rounded-full">
                    <IconComponent className="text-muted-foreground h-4 w-4" />
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-foreground mb-1 text-sm font-medium">
                    {feature.title}
                  </h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
