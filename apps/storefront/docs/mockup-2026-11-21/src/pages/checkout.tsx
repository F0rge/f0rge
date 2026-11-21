import CompactCart from '@/components/blocks/ecommerce/shopping-cart/compact-cart';
import { Block } from '@/components/block';
import { CheckoutForm } from '@/components/checkout-form';
import { Placeholder } from '@/components/photo';
import { bagCopy, formatPrice, stockLabel } from '@/content';
import { useBag } from '@/lib/bag';

export default function CheckoutPage() {
  const { items, count, subtotal, setQty, remove } = useBag();

  return (
    <div className="container mx-auto px-4 py-12 md:px-6 2xl:max-w-[1400px]">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:items-start">
        <div>
          <Block name="checkout-form" original>
            <CheckoutForm />
          </Block>
        </div>

        <div>
          <Block name="shopping-cart/compact-cart" collection="ecommerce">
            <CompactCart
              items={items.map((item) => ({
                id: item.sku,
                name: item.piece.name,
                detail: `${item.piece.room} · ${stockLabel(item.piece)}`,
                price: formatPrice(item.lineTotal),
                quantity: item.qty,
                max: item.piece.stock,
                image: <Placeholder label={item.piece.name} className="min-h-0 p-2" />,
              }))}
              totalItems={count}
              onQuantityChange={setQty}
              onRemove={remove}
              title="Your order"
              emptyText={bagCopy.empty}
              summaryTitle="Order summary"
              subtotal={formatPrice(subtotal)}
              deliveryCost={bagCopy.deliveryCost}
              total={formatPrice(subtotal)}
              totalNote={bagCopy.totalNote}
              note="Prices in rand, VAT included."
              action={{ label: 'Edit bag', to: 'bag' }}
            />
          </Block>
        </div>
      </div>
    </div>
  );
}
