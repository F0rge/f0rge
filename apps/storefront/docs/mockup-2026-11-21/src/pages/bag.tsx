import ModernCart from '@/components/blocks/ecommerce/shopping-cart/modern-cart';
import CrossSellStackedList from '@/components/blocks/ecommerce/ecommerce-cross-sells/stacked-list';
import TrustGuaranteeIconList from '@/components/blocks/ecommerce/ecommerce-trust-guarantee/icon-list';
import { Block } from '@/components/block';
import { Placeholder } from '@/components/photo';
import { bagCopy, formatPrice, pieceItem, pieces, showroom, stockLabel } from '@/content';
import { useBag } from '@/lib/bag';
import { RotateCcw, Store, Truck, UserRound } from 'lucide-react';

export default function BagPage() {
  const { items, count, subtotal, setQty, remove } = useBag();
  // Up to three catalogue pieces not already in the bag.
  const others = pieces.filter((p) => !items.some((i) => i.sku === p.sku)).slice(0, 3).map(pieceItem);

  return (
    <>
      <Block name="shopping-cart/modern-cart" collection="ecommerce">
        <ModernCart
          items={items.map((item) => ({
            id: item.sku,
            name: item.piece.name,
            detail: `${item.piece.room} · ${stockLabel(item.piece)}`,
            price: formatPrice(item.lineTotal),
            quantity: item.qty,
            max: item.piece.stock,
            image: <Placeholder label={item.piece.name} className="min-h-32 md:w-32" />,
          }))}
          totalItems={count}
          onQuantityChange={setQty}
          onRemove={remove}
          title={bagCopy.title}
          emptyText={bagCopy.empty}
          emptyAction={{ label: bagCopy.continue, to: 'shop' }}
          summaryTitle="Order summary"
          summaryDescription="Prices in rand, VAT included."
          deliveryLabel="Delivery or collection"
          deliveryNote={bagCopy.deliveryNote}
          subtotal={formatPrice(subtotal)}
          deliveryCost={bagCopy.deliveryCost}
          total={formatPrice(subtotal)}
          totalNote={bagCopy.totalNote}
          features={[
            'Change of mind returns within 30 days',
            'Guest checkout, no account needed',
            'Delivery in selected Gauteng areas, or collect',
          ]}
          checkout={{ label: bagCopy.checkout, to: 'checkout' }}
        />
      </Block>

      {others.length > 0 && (
        <Block name="ecommerce-cross-sells/stacked-list" collection="ecommerce">
          <CrossSellStackedList
            title="Add something else"
            products={others.map((p) => ({
              id: p.id,
              title: p.name,
              price: p.priceLabel,
              image: <Placeholder label={p.name} className="size-[60px] min-h-0 rounded-md p-1" />,
              action: { label: 'View', to: p.to },
            }))}
          />
        </Block>
      )}

      <Block name="ecommerce-trust-guarantee/icon-list" collection="ecommerce">
        <TrustGuaranteeIconList
          items={[
            { icon: Truck, title: 'Delivery', description: 'Selected Gauteng areas. The charge is confirmed before payment.' },
            { icon: Store, title: 'Collection', description: `From our showroom at ${showroom.short}.` },
            { icon: RotateCcw, title: 'Returns', description: 'Change of mind within 30 days of delivery or collection, unused.' },
            { icon: UserRound, title: 'Guest checkout', description: 'No account needed.' },
          ]}
        />
      </Block>
    </>
  );
}
