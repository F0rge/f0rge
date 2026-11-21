import { useMemo, useState } from 'react';
import SimpleBannerPromo from '@/components/blocks/ecommerce/promo-sections/simple-banner';
import FilterDemo, {
  emptyFilters,
  type FilterDemoGroups,
  type FilterState,
} from '@/components/blocks/ecommerce/category-filters/filter-demo';
import FilterDrawer from '@/components/blocks/ecommerce/category-filters/filter-drawer';
import GridList, { type GridListProduct } from '@/components/blocks/ecommerce/product-list/grid-list';
import ScrollingPreview from '@/components/blocks/ecommerce/category-preview/scrolling-preview';
import { Block } from '@/components/block';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  askRoute,
  countLabel,
  listings,
  rooms,
  type Availability,
  type ListingPage as ListingId,
  type ListItem,
} from '@/content';
import { useBag } from '@/lib/bag';

const SORTS = {
  featured: { label: 'Featured', compare: () => 0 },
  name: { label: 'Name, A to Z', compare: (a: ListItem, b: ListItem) => a.name.localeCompare(b.name) },
  // Price on request (null) sorts last either way.
  'price-asc': {
    label: 'Price, low to high',
    compare: (a: ListItem, b: ListItem) => (a.price ?? Infinity) - (b.price ?? Infinity),
  },
  'price-desc': {
    label: 'Price, high to low',
    compare: (a: ListItem, b: ListItem) => (b.price ?? -Infinity) - (a.price ?? -Infinity),
  },
} as const;
type SortKey = keyof typeof SORTS;

const availabilities: Availability[] = ['In stock', 'Made to order'];

export default function ListingPage({ listing: id }: { listing: ListingId }) {
  const listing = listings[id];
  const { add, setDrawerOpen } = useBag();
  const [filters, setFilters] = useState<FilterState>(emptyFilters);
  const [sort, setSort] = useState<SortKey>('featured');

  // Filter groups: only values present in this listing. categories = Room, brands = Availability.
  const groups: FilterDemoGroups = {
    categories: { title: 'Room', options: rooms.filter((r) => listing.items.some((i) => i.room === r)) },
    brands: {
      title: 'Availability',
      options: availabilities.filter((a) => listing.items.some((i) => i.availability === a)),
    },
  };

  const items = useMemo(
    () =>
      [...listing.items]
        .sort(SORTS[sort].compare)
        .map((item) => ({ id: item.id, category: item.room, brand: item.availability, item })),
    [listing, sort],
  );

  const toCard = ({ item }: (typeof items)[number]): GridListProduct => ({
    id: item.id,
    name: item.name,
    price: item.priceLabel,
    availabilityLabel: item.stockLabel,
    photo: item.photo,
    placeholder: item.placeholder,
    actions: item.piece
      ? [
          { label: 'View', to: item.to },
          {
            label: 'Add to bag',
            onClick: () => {
              add(item.id);
              setDrawerOpen(true);
            },
          },
        ]
      : [
          { label: 'View', to: item.to },
          { label: 'Ask us', to: askRoute },
        ],
  });

  const sortControl = (
    <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
      <SelectTrigger className="w-48" aria-label="Sort by">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {(Object.keys(SORTS) as SortKey[]).map((key) => (
          <SelectItem key={key} value={key}>
            {SORTS[key].label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );

  return (
    <>
      <Block name="promo-sections/simple-banner" collection="ecommerce">
        <SimpleBannerPromo
          title={listing.name}
          subtitle={listing.subtitle}
          primary={{ label: 'Visit the showroom', to: 'home/visit' }}
          secondary={{ label: 'Delivery and returns', to: 'help' }}
        />
      </Block>

      <Block name="category-filters/filter-demo" collection="ecommerce">
        <FilterDemo
          title={listing.page === 'shop' ? 'All pieces' : listing.name}
          filtersTitle="Filters"
          clearLabel="Clear all"
          groups={groups}
          items={items}
          filters={filters}
          onFilterChange={setFilters}
          resultLabel={countLabel}
          empty={{ title: 'No pieces found', description: 'Try clearing a filter.' }}
          toolbar={sortControl}
          mobileFilters={
            <Block name="category-filters/filter-drawer" collection="ecommerce">
              <FilterDrawer
                className="h-auto p-0"
                title="Filters"
                description="Narrow the list by room or availability."
                clearLabel="Clear all"
                applyLabel="Show pieces"
                groups={groups}
                filters={filters}
                onFilterChange={setFilters}
              />
            </Block>
          }
        >
          {(shown) => (
            <Block name="product-list/grid-list" collection="ecommerce">
              <GridList products={shown.map(toCard)} />
            </Block>
          )}
        </FilterDemo>
      </Block>

      <Block name="category-preview/scrolling-preview" collection="ecommerce">
        <ScrollingPreview
          title="Other collections"
          description="More from the showroom."
          ctaLabel="View all"
          categories={Object.values(listings)
            .filter((l) => l.page !== id)
            .map((l) => ({
              name: l.name,
              description: l.description,
              photo: l.photo,
              placeholder: l.name,
              countLabel: countLabel(l.items.length),
              to: l.page,
            }))}
        />
      </Block>
    </>
  );
}
