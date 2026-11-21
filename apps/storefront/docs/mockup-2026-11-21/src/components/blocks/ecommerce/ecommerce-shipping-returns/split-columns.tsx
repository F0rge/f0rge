import type { LucideIcon } from "lucide-react";

export interface SplitColumnsItem {
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface SplitColumnsColumn {
  title: string;
  items: SplitColumnsItem[];
}

export default function ShippingReturnsSplitColumns({
  columns,
}: {
  /** Two columns: delivery, then returns. */
  columns: [SplitColumnsColumn, SplitColumnsColumn];
}) {
  return (
    <div className="px-4 py-8 md:py-12">
      <div className="container mx-auto">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-2 md:gap-12">
          {columns.map((column) => (
            <div key={column.title} className="space-y-6">
              <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
                {column.title}
              </h2>

              {column.items.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="flex items-start gap-3">
                    <div className="bg-muted mt-1 rounded-md p-2">
                      <Icon className="text-muted-foreground h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium">{item.title}</h3>
                      <p className="text-muted-foreground mt-1">
                        {item.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
