import LargeImageSplitPromo from '@/components/blocks/ecommerce/promo-sections/large-image-split';
import ThreeColumnPreview from '@/components/blocks/ecommerce/category-preview/three-column-preview';
import FeaturedList, { type FeaturedListProduct } from '@/components/blocks/ecommerce/product-list/featured-list';
import ImageAsidePromo from '@/components/blocks/ecommerce/promo-sections/image-aside';
import QuickContactCTA from '@/components/blocks/marketing/cta-sections/quick-contact-cta';
import CenterAlignedFaq from '@/components/blocks/marketing/faq-sections/center-aligned';
import { Block } from '@/components/block';
import {
  arc,
  askRoute,
  contactCopy,
  countLabel,
  faqs,
  listings,
  photos,
  pieceItem,
  pieces,
  showroom,
  type ListItem,
} from '@/content';
import { useBag } from '@/lib/bag';

// Featured first, then four more from the catalogue.
const featuredSku = 'P003340AD';
const otherSkus = ['P00332AD', 'P00342AD', 'P00300', '60244'];
const bySku = (sku: string) => pieceItem(pieces.find((p) => p.sku === sku)!);

export default function HomePage() {
  const { add, setDrawerOpen } = useBag();

  const toCard = (item: ListItem): FeaturedListProduct => ({
    id: item.id,
    name: item.name,
    description: `${item.description} · ${item.stockLabel}`,
    price: item.priceLabel,
    photo: item.photo,
    placeholder: item.placeholder,
    actions: [
      { label: 'View', to: item.to },
      {
        label: 'Add to bag',
        onClick: () => {
          add(item.id);
          setDrawerOpen(true);
        },
      },
    ],
  });

  return (
    <>
      <Block name="promo-sections/large-image-split" collection="ecommerce">
        <LargeImageSplitPromo
          badge="Bedford Square, Bedfordview"
          title="Furniture for living and dining rooms"
          description="Sofas, dining tables and chairs, and pieces for the living room and bedroom. Shop online or visit our showroom, open seven days a week."
          primary={{ label: 'Shop all', to: 'shop' }}
          secondary={{ label: 'Visit the showroom', to: 'home/visit' }}
          photo={photos.front}
          placeholder={arc.name}
        />
      </Block>

      <Block name="category-preview/three-column-preview" collection="ecommerce">
        <ThreeColumnPreview
          ctaLabel="Shop now"
          categories={(['sofas', 'dining-room', 'on-sale'] as const).map((page) => {
            const l = listings[page];
            return {
              name: l.name,
              description: l.description,
              photo: l.photo,
              placeholder: l.name,
              countLabel: countLabel(l.items.length),
              to: l.page,
            };
          })}
        />
      </Block>

      <Block name="product-list/featured-list" collection="ecommerce">
        <FeaturedList
          featuredBadge="In stock"
          featured={toCard(bySku(featuredSku))}
          products={otherSkus.map((sku) => toCard(bySku(sku)))}
        />
      </Block>

      <Block name="promo-sections/image-aside" collection="ecommerce">
        <ImageAsidePromo
          badge={arc.availability}
          eyebrow={arc.room}
          title={arc.name}
          description={arc.short}
          points={[
            { term: 'Cushion fill', detail: `${arc.fill}.` },
            { term: 'Made to order', detail: 'Made for your order.' },
            { term: 'Price', detail: 'On request.' },
          ]}
          primary={{ label: 'View the Arc sofa', to: 'arc' }}
          secondary={{ label: 'Ask about this piece', to: askRoute }}
          photo={photos.angle}
          placeholder={arc.name}
        />
      </Block>

      <Block name="cta-sections/quick-contact-cta" collection="marketing">
        <QuickContactCTA
          id="visit"
          title="Visit the showroom"
          description={`See the pieces in person at ${showroom.name}. ${showroom.note}`}
          address={{ title: 'Address', description: showroom.name, value: showroom.address }}
          hours={{ title: 'Opening hours', rows: showroom.hours }}
          phones={{ title: 'Call us', numbers: showroom.phones }}
          email={{ title: 'Email', description: 'For questions about a piece or an order.', value: showroom.email }}
          form={{
            title: 'Send us a message',
            subjects: ['A piece in the shop', 'The Arc sofa', 'Delivery or collection', 'Returns', 'Something else'],
            submitLabel: 'Send message',
            submittedNote: contactCopy.notSent,
          }}
        />
      </Block>

      <Block name="faq-sections/center-aligned" collection="marketing">
        <CenterAlignedFaq
          title="Questions"
          description="About the showroom, delivery and returns."
          faqs={faqs}
        />
      </Block>
    </>
  );
}
