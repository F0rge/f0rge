import { Check } from "lucide-react";
import { Link, type Route } from "@/lib/router";

export interface TrustGuaranteeChecklistProps {
  title: string;
  description: string;
  items: { title: string; description: string }[];
  footer: { text: string; link: { label: string; to: Route } };
}

export default function TrustGuaranteeChecklist({ title, description, items, footer }: TrustGuaranteeChecklistProps) {
  const trustItems = items;

  return (
    <div className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 text-center">
          <h2 className="mb-2 text-2xl font-bold md:text-3xl">
            {title}
          </h2>
          <p className="text-muted-foreground">
            {description}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
          {trustItems.map((item, index) => {
            return (
              <div
                key={index}
                className="bg-card flex items-start gap-3 rounded-lg border p-4"
              >
                <div className="bg-primary mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full">
                  <Check className="text-primary-foreground h-4 w-4" />
                </div>
                <div className="flex flex-1 items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm leading-tight font-semibold md:text-base">
                      {item.title}
                    </h3>
                    <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                      {item.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-8 text-center">
          <p className="text-muted-foreground text-sm">
            {footer.text}{" "}
            <Link to={footer.link.to} className="text-primary cursor-pointer font-medium hover:underline">
              {footer.link.label}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
