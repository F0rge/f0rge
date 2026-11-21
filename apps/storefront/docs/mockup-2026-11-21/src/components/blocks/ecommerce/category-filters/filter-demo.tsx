import * as React from 'react';
import { useState, useCallback, useMemo } from 'react';
import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

/**
 * Filter state, keyed as in the installed block. `categories` and `brands` filter the
 * items. `colors` and `sizes` are kept for the block's shape; their groups render only when
 * given, and they do not filter.
 */
export interface FilterState {
  categories: string[];
  brands: string[];
  colors: string[];
  sizes: string[];
}

/** What the filtering reads from each item. */
export interface FilterDemoItem {
  id: string;
  /** Matched against the `categories` group. */
  category: string;
  /** Matched against the `brands` group. */
  brand: string;
}

export interface FilterDemoGroups {
  categories: { title: string; options: string[] };
  brands: { title: string; options: string[] };
  colors?: { title: string; options: { name: string; value: string; light?: boolean }[] };
  sizes?: { title: string; options: string[] };
}

export interface FilterDemoProps<T extends FilterDemoItem> {
  title: string;
  filtersTitle: string;
  clearLabel: string;
  groups: FilterDemoGroups;
  items: T[];
  /** Controlled, so the small-screen drawer can share it. */
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  resultLabel: (count: number) => string;
  empty: { title: string; description: string };
  /** Rendered beside the result count (the listing's sort control). */
  toolbar?: React.ReactNode;
  /** Small-screen filter UI (the filter-drawer block), shown below `lg`. */
  mobileFilters?: React.ReactNode;
  /** Renders the filtered items (the grid-list block). */
  children: (items: T[]) => React.ReactNode;
}

export const emptyFilters: FilterState = { categories: [], brands: [], colors: [], sizes: [] };

const slug = (value: string) => value.replace(/\W+/g, '-');

export default function FilterDemo<T extends FilterDemoItem>({
  title,
  filtersTitle,
  clearLabel,
  groups,
  items,
  filters,
  onFilterChange,
  resultLabel,
  empty,
  toolbar,
  mobileFilters,
  children,
}: FilterDemoProps<T>) {
  // Filter products based on selected filters - memoized to prevent recalculation
  const filteredProducts = useMemo(() => {
    return items.filter((product) => {
      // Category filter
      if (
        filters.categories.length > 0 &&
        !filters.categories.includes(product.category)
      ) {
        return false;
      }

      // Brand filter
      if (
        filters.brands.length > 0 &&
        !filters.brands.includes(product.brand)
      ) {
        return false;
      }

      return true;
    });
  }, [filters, items]);

  return (
    <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
      <h1 className="mb-6 text-2xl font-bold">{title}</h1>

      <div className="flex flex-col gap-8 lg:flex-row">
        {/* Sidebar Filters */}
        <SidebarFilters
          title={filtersTitle}
          clearLabel={clearLabel}
          groups={groups}
          filters={filters}
          onFilterChange={onFilterChange}
          mobileFilters={mobileFilters}
          items={items}
        />

        {/* Product Grid */}
        <div className="flex-1">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="text-muted-foreground text-sm" aria-live="polite">
              {resultLabel(filteredProducts.length)}
            </div>
            {toolbar}
          </div>

          {filteredProducts.length > 0 && children(filteredProducts)}

          {filteredProducts.length === 0 && (
            <div className="py-12 text-center">
              <h3 className="text-lg font-medium">{empty.title}</h3>
              <p className="text-muted-foreground mt-1">
                {empty.description}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Sidebar Filters Component
function SidebarFilters({
  title,
  clearLabel,
  groups,
  filters,
  onFilterChange,
  mobileFilters,
  items,
}: {
  items: FilterDemoItem[];
  title: string;
  clearLabel: string;
  groups: FilterDemoGroups;
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  mobileFilters?: React.ReactNode;
}) {
  const activeFiltersCount =
    filters.categories.length + filters.brands.length + filters.colors.length + filters.sizes.length;

  const toggleFilter = useCallback(
    (type: keyof FilterState, value: string) => {
      const currentValues = filters[type];
      const newValues = currentValues.includes(value)
        ? currentValues.filter((v) => v !== value)
        : [...currentValues, value];
      onFilterChange({ ...filters, [type]: newValues });
    },
    [filters, onFilterChange]
  );

  const clearFilters = useCallback(() => {
    onFilterChange(emptyFilters);
  }, [onFilterChange]);

  const categories = groups.categories.options;
  const brands = groups.brands.options;
  const colors = groups.colors?.options ?? [];
  const sizes = groups.sizes?.options ?? [];
  const countOf = (key: 'category' | 'brand', value: string) =>
    items.filter((item) => item[key] === value).length;

  const FilterSection = ({
    title,
    children,
    defaultOpen = true,
  }: {
    title: string;
    children: React.ReactNode;
    defaultOpen?: boolean;
  }) => {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
      <Collapsible open={isOpen} onOpenChange={setIsOpen} className="w-full">
        <div className="flex items-center justify-between py-2">
          <h3 className="text-sm font-medium">{title}</h3>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" aria-label={title}>
              {isOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="pb-4">{children}</CollapsibleContent>
        <Separator />
      </Collapsible>
    );
  };

  return (
    <>
      {/* Mobile filters: the filter-drawer block */}
      {mobileFilters && <div className="lg:hidden">{mobileFilters}</div>}

      {/* Desktop Filters */}
      <div className="hidden w-64 shrink-0 lg:block">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          {activeFiltersCount > 0 && (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              {clearLabel}
            </Button>
          )}
        </div>
        <FilterContent />
      </div>
    </>
  );

  function FilterContent() {
    return (
      <div className="space-y-1">
        <FilterSection title={groups.categories.title}>
          <div className="space-y-2">
            {categories.map((category) => (
              <div key={category} className="flex items-center space-x-2">
                <Checkbox
                  id={`category-${slug(category)}`}
                  checked={filters.categories.includes(category)}
                  onCheckedChange={() => toggleFilter('categories', category)}
                />
                <label
                  htmlFor={`category-${slug(category)}`}
                  className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {category}{' '}
                  <span className="text-muted-foreground">({countOf('category', category)})</span>
                </label>
              </div>
            ))}
          </div>
        </FilterSection>

        <FilterSection title={groups.brands.title}>
          <div className="space-y-2">
            {brands.map((brand) => (
              <div key={brand} className="flex items-center space-x-2">
                <Checkbox
                  id={`brand-${slug(brand)}`}
                  checked={filters.brands.includes(brand)}
                  onCheckedChange={() => toggleFilter('brands', brand)}
                />
                <label
                  htmlFor={`brand-${slug(brand)}`}
                  className="text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {brand}{' '}
                  <span className="text-muted-foreground">({countOf('brand', brand)})</span>
                </label>
              </div>
            ))}
          </div>
        </FilterSection>

        {groups.colors && (
        <FilterSection title={groups.colors.title}>
          <div className="grid grid-cols-4 gap-2">
            {colors.map((color) => (
              <div
                key={color.name}
                className="flex flex-col items-center gap-1"
              >
                <button
                  className={cn(
                    'border-input flex h-8 w-8 items-center justify-center rounded-full border',
                    filters.colors.includes(color.name) && 'ring-primary ring-2'
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
        </FilterSection>
        )}

        {groups.sizes && (
        <FilterSection title={groups.sizes.title}>
          <div className="grid grid-cols-3 gap-2">
            {sizes.map((size) => (
              <Button
                key={size}
                variant={filters.sizes.includes(size) ? 'default' : 'outline'}
                size="sm"
                onClick={() => toggleFilter('sizes', size)}
                className="h-8"
                aria-pressed={filters.sizes.includes(size)}
              >
                {size}
              </Button>
            ))}
          </div>
        </FilterSection>
        )}
      </div>
    );
  }
}
