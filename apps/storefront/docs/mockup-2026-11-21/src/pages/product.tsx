import { useState } from 'react';
import GalleryOverview from '@/components/blocks/ecommerce/product-overview/gallery-overview';
import ShippingReturnsWithIcons from '@/components/blocks/ecommerce/ecommerce-shipping-returns/with-icons';
import TrustGuaranteeChecklist from '@/components/blocks/ecommerce/ecommerce-trust-guarantee/checklist';
import CrossSellSimpleGrid from '@/components/blocks/ecommerce/ecommerce-cross-sells/simple-grid';
import { Block } from '@/components/block';
import {
  findPiece,
  formatPrice,
  policy,
  relatedTo,
  showroom,
  stockLabel,
} from '@/content';
import { useBag } from '@/lib/bag';
import { navigate, type Page } from '@/lib/router';

/** Short lines for the overview's three-column strip (shared with the Arc page). */
export const overviewAssurances = [
  { title: 'Delivery', description: 'Selected Gauteng areas' },
  { title: 'Collection', description: 'Bedford Square showroom' },
  { title: 'Returns', description: 'Change of mind within 30 days' },
];

export const shippingReturns = {
  shipping: {
    title: 'Delivery or collection',
    body: `${policy.delivery} ${policy.deliveryCharges} ${policy.collection}`,
  },
  returns: {
    title: 'Returns',
    body: `Change of mind: within 30 days of delivery or collection, unused and in the original condition and packaging. ${policy.contactFirst}`,
  },
};

/** One template for every catalogue piece (#p-<sku>). */
export default function ProductPage({ page }: { page: Page }) {
  const piece = findPiece(page)!; // the router only sends known product pages here
  const { add, setDrawerOpen } = useBag();
  const [qty, setQty] = useState('1');
  const quantities = Array.from({ length: piece.stock }, (_, i) => String(i + 1));

  return (
    <>
      <Block name="product-overview/gallery-overview" collection="ecommerce">
        <GalleryOverview
          eyebrow={piece.room}
          name={piece.name}
          price={formatPrice(piece.price)}
          priceNote={`incl. VAT · SKU ${piece.sku} · ${stockLabel(piece)}`}
          description={`In stock. Delivery in selected Gauteng areas, or collect from our showroom at ${showroom.short}.`}
          points={piece.details}
          images={[{ placeholder: piece.name }]}
          option={{ label: 'Quantity', values: quantities, selected: qty, onSelect: setQty }}
          primary={{
            label: 'Add to bag',
            onClick: () => {
              add(piece.sku, Number(qty));
              setDrawerOpen(true);
            },
          }}
          secondary={{
            label: 'Buy now',
            onClick: () => {
              add(piece.sku, Number(qty));
              navigate('checkout');
            },
          }}
          assurances={overviewAssurances}
        />
      </Block>

      <Block name="ecommerce-shipping-returns/with-icons" collection="ecommerce">
        <ShippingReturnsWithIcons {...shippingReturns} />
      </Block>

      <Block name="ecommerce-trust-guarantee/checklist" collection="ecommerce">
        <TrustGuaranteeChecklist
          title="Buying from DasKasas"
          description="What applies to this piece."
          items={[
            { title: stockLabel(piece), description: `SKU ${piece.sku}.` },
            { title: 'Price includes VAT', description: `${formatPrice(piece.price)} each, in rand.` },
            { title: 'Delivery or collection', description: 'Selected Gauteng areas, or collect from Bedford Square.' },
            { title: 'Change of mind', description: 'Return within 30 days of delivery or collection, unused.' },
            { title: 'Faulty furniture', description: 'Claims within 12 months of purchase, under the Consumer Protection Act.' },
            { title: 'Guest checkout', description: 'No account needed.' },
          ]}
          footer={{ text: 'Questions about this piece?', link: { label: 'Contact us', to: 'help/contact' } }}
        />
      </Block>

      <Block name="ecommerce-cross-sells/simple-grid" collection="ecommerce">
        <CrossSellSimpleGrid
          title="More pieces"
          ctaLabel="View"
          products={relatedTo(piece.room, piece.sku).map((i) => ({
            id: i.id,
            name: i.name,
            description: i.description,
            price: i.priceLabel,
            photo: i.photo,
            placeholder: i.placeholder,
            to: i.to,
          }))}
        />
      </Block>
    </>
  );
}
