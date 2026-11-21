import { useState } from 'react';
import { Check, Filter, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

export interface FilterDrawerState {
  categories: string[];
  brands: string[];
  colors: string[];
  sizes: string[];
}

export interface FilterDrawerGroups {
  categories: { title: string; options: string[] };
  brands: { title: string; options: string[] };
  colors?: { title: string; options: { name: string; value: string; light?: boolean }[] };
  sizes?: { title: string; options: string[] };
}

interface FilterDrawerProps {
  className?: string;
  title: string;
  description: string;
  clearLabel: string;
  applyLabel: string;
  groups: FilterDrawerGroups;
  /** Controlled, so the desktop sidebar (filter-demo) can share it. */
  filters: FilterDrawerState;
  onFilterChange: (filters: FilterDrawerState) => void;
}

// The installed price-range slider is removed: it had no real values behind it.
const slug = (value: string) => value.replace(/\W+/g, '-');

export default function FilterDrawer({
  className,
  title,
  description,
  clearLabel,
  applyLabel,
  groups,
  filters,
  onFilterChange,
}: FilterDrawerProps) {
  const [open, setOpen] = useState(false);

  // Count active filters
  const activeFiltersCount =
    filters.categories.length +
    filters.brands.length +
    filters.colors.length +
    filters.sizes.length;

  const toggleFilter = (type: keyof FilterDrawerState, value: string) => {
    const currentValues = filters[type];
    const newValues = currentValues.includes(value)
      ? currentValues.filter((v) => v !== value)
      : [...currentValues, value];

    onFilterChange({ ...filters, [type]: newValues });
  };

  const clearFilters = () => {
    onFilterChange({ categories: [], brands: [], colors: [], sizes: [] });
  };

  const categories = groups.categories.options;
  const brands = groups.brands.options;
  const colors = groups.colors?.options ?? [];
  const sizes = groups.sizes?.options ?? [];

  const ActiveFilterBadges = () => {
    const activeFilters = [
      ...filters.categories.map((cat) => ({ type: 'categories', value: cat })),
      ...filters.brands.map((brand) => ({ type: 'brands', value: brand })),
      ...filters.colors.map((color) => ({ type: 'colors', value: color })),
      ...filters.sizes.map((size) => ({ type: 'sizes', value: size })),
    ];

    if (activeFilters.length === 0) return null;

    return (
      <div className="mt-3 flex flex-wrap gap-2">
        {activeFilters.map((filter, index) => (
          <Badge
            key={`${filter.type}-${filter.value}-${index}`}
            variant="outline"
            className="flex items-center gap-1 px-2 py-1"
          >
            {filter.value}
            <Button
              variant="ghost"
              size="icon"
              className="ml-1 h-4 w-4 p-0"
              aria-label={`Remove ${filter.value}`}
              onClick={() =>
                toggleFilter(filter.type as keyof FilterDrawerState, filter.value)
              }
            >
              <X className="h-3 w-3" />
            </Button>
          </Badge>
        ))}
        {activeFilters.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={clearFilters}
          >
            {clearLabel}
          </Button>
        )}
      </div>
    );
  };

  return (
    <>
      {/* Height is set to 800px for demo purposes */}
      <div className={cn('h-[800px] w-full p-6', className)}>
        <div className="mb-4 flex items-center justify-between">
          <Drawer open={open} onOpenChange={setOpen}>
            <DrawerTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="flex items-center gap-2"
              >
                <Filter className="h-4 w-4" />
                {title}
                {activeFiltersCount > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {activeFiltersCount}
                  </Badge>
                )}
              </Button>
            </DrawerTrigger>
            <DrawerContent>
              <DrawerHeader className="border-b pb-4">
                <DrawerTitle>{title}</DrawerTitle>
                <DrawerDescription>
                  {description}
                </DrawerDescription>
              </DrawerHeader>
              <ScrollArea className="h-[60vh] px-4 py-2">
                <Accordion type="multiple" className="w-full">
                  <AccordionItem value="categories">
                    <AccordionTrigger className="py-3">
                      {groups.categories.title}
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-2">
                        {categories.map((category) => (
                          <div
                            key={category}
                            className="flex items-center space-x-2"
                          >
                            <Checkbox
                              id={`drawer-category-${slug(category)}`}
                              checked={filters.categories.includes(category)}
                              onCheckedChange={() =>
                                toggleFilter('categories', category)
                              }
                            />
                            <label
                              htmlFor={`drawer-category-${slug(category)}`}
                              className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                            >
                              {category}
                            </label>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  <AccordionItem value="brands">
                    <AccordionTrigger className="py-3">{groups.brands.title}</AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-2">
                        {brands.map((brand) => (
                          <div
                            key={brand}
                            className="flex items-center space-x-2"
                          >
                            <Checkbox
                              id={`drawer-brand-${slug(brand)}`}
                              checked={filters.brands.includes(brand)}
                              onCheckedChange={() =>
                                toggleFilter('brands', brand)
                              }
                            />
                            <label
                              htmlFor={`drawer-brand-${slug(brand)}`}
                              className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                            >
                              {brand}
                            </label>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>

                  {groups.colors && (
                  <AccordionItem value="colors">
                    <AccordionTrigger className="py-3">{groups.colors.title}</AccordionTrigger>
                    <AccordionContent>
                      <div className="grid grid-cols-4 gap-3">
                        {colors.map((color) => (
                          <div
                            key={color.name}
                            className="flex flex-col items-center gap-1"
                          >
                            <button
                              className={cn(
                                'border-input flex h-8 w-8 items-center justify-center rounded-full border',
                                filters.colors.includes(color.name) &&
                                  'ring-primary ring-2'
                              )}
                              style={{ backgroundColor: color.value }}
                              onClick={() => toggleFilter('colors', color.name)}
                              aria-pressed={filters.colors.includes(color.name)}
                              aria-label={color.name}
                            >
                              {filters.colors.includes(color.name) && (
                                <Check
                                  className={cn(
                                    'h-4 w-4',
                                    color.light
                                      ? 'text-black'
                                      : 'text-white'
                                  )}
                                />
                              )}
                            </button>
                            <span className="text-xs">{color.name}</span>
                          </div>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                  )}

                  {groups.sizes && (
                  <AccordionItem value="sizes" className="border-b-0">
                    <AccordionTrigger className="py-3">{groups.sizes.title}</AccordionTrigger>
                    <AccordionContent>
                      <div className="grid grid-cols-3 gap-2">
                        {sizes.map((size) => (
                          <Button
                            key={size}
                            variant={
                              filters.sizes.includes(size)
                                ? 'default'
                                : 'outline'
                            }
                            size="sm"
                            onClick={() => toggleFilter('sizes', size)}
                            className="h-8"
                          >
                            {size}
                          </Button>
                        ))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                  )}

                </Accordion>
              </ScrollArea>
              <DrawerFooter className="border-t pt-4">
                <div className="flex w-full items-center justify-between">
                  <Button variant="outline" onClick={clearFilters}>
                    {clearLabel}
                  </Button>
                  <DrawerClose asChild>
                    <Button>{applyLabel}</Button>
                  </DrawerClose>
                </div>
              </DrawerFooter>
            </DrawerContent>
          </Drawer>

          {activeFiltersCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="hidden sm:flex"
            >
              {clearLabel}
            </Button>
          )}
        </div>

        {/* Active Filter Badges */}
        <ActiveFilterBadges />

        <Separator className="my-4" />
      </div>
    </>
  );
}
