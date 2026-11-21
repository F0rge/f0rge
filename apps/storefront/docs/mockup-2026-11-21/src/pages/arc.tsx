import { Armchair, Hammer, Layers, MessageCircle, Ruler, Sofa, Tag, Truck } from 'lucide-react';
import GalleryOverview from '@/components/blocks/ecommerce/product-overview/gallery-overview';
import FeatureTabsNavigation from '@/components/blocks/ecommerce/product-features/feature-tabs-navigation';
import SplitImageFeatures from '@/components/blocks/ecommerce/product-features/split-image-features';
import ShippingReturnsWithIcons from '@/components/blocks/ecommerce/ecommerce-shipping-returns/with-icons';
import TrustGuaranteeChecklist from '@/components/blocks/ecommerce/ecommerce-trust-guarantee/checklist';
import UpsellBundleSideBySide from '@/components/blocks/ecommerce/ecommerce-bundle-upsells/side-by-side';
import CrossSellSimpleGrid from '@/components/blocks/ecommerce/ecommerce-cross-sells/simple-grid';
import { Block } from '@/components/block';
import {
  arc,
  askRoute,
  crops,
  formatPrice,
  pieceRoute,
  pieces,
  photos,
  policy,
  relatedTo,
  stockLabel,
} from '@/content';
import { navigate } from '@/lib/router';
import { overviewAssurances, shippingReturns } from '@/pages/product';

const coffeeTable = pieces.find((p) => p.sku === 'P00300')!;

export default function ArcPage() {
  return (
    <>
      <Block name="product-overview/gallery-overview" collection="ecommerce">
        <GalleryOverview
          eyebrow={`${arc.room} · ${arc.availability}`}
          name={arc.name}
          price={arc.priceLabel}
          description={arc.short}
          points={[arc.fill, 'Made to order']}
          images={[
            { photo: photos.front, placeholder: arc.name },
            { photo: photos.angle, placeholder: arc.name },
            { photo: photos.detail, placeholder: arc.name },
          ]}
          primary={{ label: 'Ask about this piece', onClick: () => navigate(askRoute) }}
          assurances={overviewAssurances}
        />
      </Block>

      <Block name="product-features/feature-tabs-navigation" collection="ecommerce">
        <FeatureTabsNavigation
          badge="Details"
          title="The Arc sofa"
          description={arc.short}
          tabs={[
            {
              id: 'shape',
              label: 'Shape',
              icon: Sofa,
              title: 'A curved three-seater',
              description: 'The Arc sofa is a curved sofa that seats three.',
              photo: photos.front,
              placeholder: arc.name,
              link: { label: 'Shop sofas', to: 'sofas' },
              features: [
                { icon: Armchair, title: 'Three seats', description: 'Room for three.' },
                { icon: Ruler, title: 'Curved', description: 'A curved shape rather than a straight run.' },
              ],
            },
            {
              id: 'fill',
              label: 'Cushion fill',
              icon: Layers,
              title: 'Soft or Firm',
              description: `${arc.fill}.`,
              photo: crops.cushion,
              placeholder: arc.name,
              link: { label: 'Ask about this piece', to: askRoute },
              features: [
                { icon: Layers, title: 'Soft', description: 'The softer of the two fills.' },
                { icon: Layers, title: 'Firm', description: 'The firmer of the two fills.' },
              ],
            },
            {
              id: 'made-to-order',
              label: 'Made to order',
              icon: Hammer,
              title: 'Made for your order',
              description: 'The Arc sofa is made to order.',
              photo: photos.angle,
              placeholder: arc.name,
              link: { label: 'Ask about this piece', to: askRoute },
              features: [
                { icon: Hammer, title: 'Made to order', description: 'Made after you order it.' },
                { icon: Truck, title: 'Delivery or collection', description: 'Selected Gauteng areas, or collect from the showroom.' },
              ],
            },
            {
              id: 'price',
              label: 'Price',
              icon: Tag,
              title: 'Price on request',
              description: 'Contact us for the price of the Arc sofa.',
              photo: crops.plinth,
              placeholder: arc.name,
              link: { label: 'Ask about this piece', to: askRoute },
              features: [
                { icon: MessageCircle, title: 'Ask us', description: 'Call, email or visit the showroom.' },
                { icon: Tag, title: 'Prices in rand', description: 'All our prices include VAT.' },
              ],
            },
          ]}
          specsTitle="At a glance"
          specs={[
            { label: 'Seats', value: 'Three' },
            { label: 'Shape', value: 'Curved' },
            { label: 'Cushion fill', value: 'Soft or Firm' },
            { label: 'Availability', value: 'Made to order' },
          ]}
          primary={{ label: 'Ask about this piece', to: askRoute }}
          secondary={{ label: 'Shop sofas', to: 'sofas' }}
        />
      </Block>

      <Block name="product-features/split-image-features" collection="ecommerce">
        <SplitImageFeatures
          badge="Close-up"
          title="Arm, cushion and plinth"
          description="A closer look at the Arc sofa."
          images={[
            { photo: photos.detail, placeholder: arc.name },
            { photo: crops.cushion, placeholder: arc.name },
            { photo: crops.plinth, placeholder: arc.name },
            { photo: photos.angle, placeholder: arc.name },
          ]}
          features={[
            { title: 'Cushions', description: `${arc.fill}.` },
            { title: 'Made to order', description: 'Made after you order it.' },
            { title: 'Price on request', description: 'Contact us for the price.' },
          ]}
          divider="Questions about the Arc sofa?"
          primary={{ label: 'Ask about this piece', to: askRoute }}
          secondary={{ label: 'Shop sofas', to: 'sofas' }}
        />
      </Block>

      <Block name="ecommerce-shipping-returns/with-icons" collection="ecommerce">
        <ShippingReturnsWithIcons
          shipping={shippingReturns.shipping}
          returns={{
            title: 'Returns',
            body: `Pieces made to a measurement, fabric or finish chosen for your order can’t be returned for a change of mind. ${policy.wrongItem}`,
          }}
        />
      </Block>

      <Block name="ecommerce-trust-guarantee/checklist" collection="ecommerce">
        <TrustGuaranteeChecklist
          title="Buying the Arc sofa"
          description="What applies to this piece."
          items={[
            { title: 'Made to order', description: 'Made after you order it.' },
            { title: 'Cushion fill', description: 'Soft or Firm.' },
            { title: 'Price on request', description: 'Contact us for the price.' },
            { title: 'Delivery or collection', description: 'Selected Gauteng areas, or collect from Bedford Square.' },
            { title: 'Faulty furniture', description: 'Claims within 12 months of purchase, under the Consumer Protection Act.' },
            { title: 'Prices in rand', description: 'VAT included.' },
          ]}
          footer={{ text: 'Questions about the Arc sofa?', link: { label: 'Contact us', to: askRoute } }}
        />
      </Block>

      <Block name="ecommerce-bundle-upsells/side-by-side" collection="ecommerce">
        <UpsellBundleSideBySide
          title="Pairs well"
          description="The Arc sofa with the Ostrich leather coffee table."
          addOnsTitle="Pairs well with"
          summaryTitle="Together"
          mainProduct={{
            name: arc.name,
            price: arc.priceLabel,
            photo: photos.front,
            placeholder: arc.name,
            description: arc.short,
          }}
          addOns={[
            {
              id: coffeeTable.sku,
              name: coffeeTable.name,
              price: formatPrice(coffeeTable.price),
              placeholder: coffeeTable.name,
              description: `${coffeeTable.details.join(' · ')} · ${stockLabel(coffeeTable)}`,
            },
          ]}
          cta={{ label: 'View the coffee table', to: pieceRoute(coffeeTable) }}
        />
      </Block>

      <Block name="ecommerce-cross-sells/simple-grid" collection="ecommerce">
        <CrossSellSimpleGrid
          title="More pieces"
          ctaLabel="View"
          products={relatedTo('Living room', 'arc').map((i) => ({
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
