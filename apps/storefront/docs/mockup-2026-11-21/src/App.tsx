import SimpleCentered from '@/components/blocks/marketing/announcement-banners/simple-centered';
import EcommerceFooterMultiColumn from '@/components/blocks/ecommerce/ecommerce-footers/muti-column';
import SidebarCart from '@/components/blocks/ecommerce/shopping-cart/sidebar-cart';
import { Block } from '@/components/block';
import { Navbar, Wordmark } from '@/components/navbar';
import { Placeholder } from '@/components/photo';
import { announcement, bagCopy, brand, footer, formatPrice, stockLabel } from '@/content';
import { BagProvider, useBag } from '@/lib/bag';
import { navigate, useRoute, useScrollOnNavigate, type Page } from '@/lib/router';
import ArcPage from '@/pages/arc';
import BagPage from '@/pages/bag';
import CheckoutPage from '@/pages/checkout';
import HelpPage from '@/pages/help';
import HomePage from '@/pages/home';
import ListingPage from '@/pages/listing';
import ProductPage from '@/pages/product';

function renderPage(page: Page) {
  switch (page) {
    case 'home':
      return <HomePage />;
    case 'shop':
    case 'sofas':
    case 'dining-room':
    case 'on-sale':
      return <ListingPage key={page} listing={page} />;
    case 'arc':
      return <ArcPage />;
    case 'bag':
      return <BagPage />;
    case 'checkout':
      return <CheckoutPage />;
    case 'help':
      return <HelpPage />;
    default:
      return <ProductPage key={page} page={page} />;
  }
}

function BagDrawer() {
  const { items, count, subtotal, setQty, remove, drawerOpen, setDrawerOpen } = useBag();
  const close = () => setDrawerOpen(false);
  return (
    <Block name="shopping-cart/sidebar-cart" collection="ecommerce">
      <SidebarCart
        isOpen={drawerOpen}
        onClose={close}
        totalItems={count}
        items={items.map((item) => ({
          id: item.sku,
          name: item.piece.name,
          detail: `${item.piece.room} · ${stockLabel(item.piece)}`,
          price: formatPrice(item.lineTotal),
          quantity: item.qty,
          max: item.piece.stock,
          image: <Placeholder label={item.piece.name} className="min-h-0 p-1" />,
        }))}
        onQuantityChange={setQty}
        onRemove={remove}
        title={bagCopy.title}
        emptyText={bagCopy.empty}
        deliveryNote={bagCopy.deliveryNote}
        subtotal={formatPrice(subtotal)}
        deliveryCost={bagCopy.deliveryCost}
        total={formatPrice(subtotal)}
        totalNote={bagCopy.totalNote}
        checkoutLabel={bagCopy.checkout}
        continueLabel={bagCopy.continue}
        onCheckout={() => {
          close();
          navigate('checkout');
        }}
      />
    </Block>
  );
}

function Shell() {
  const page = useRoute();
  useScrollOnNavigate();
  return (
    <div className="flex min-h-svh flex-col">
      <Block name="announcement-banners/simple-centered" collection="marketing">
        <SimpleCentered {...announcement} />
      </Block>
      <Block name="navbar" original>
        <Navbar />
      </Block>
      <main className="flex-1">{renderPage(page)}</main>
      <Block name="ecommerce-footers/muti-column" collection="ecommerce">
        <EcommerceFooterMultiColumn
          brand={<Wordmark className="text-3xl" />}
          blurb={footer.blurb}
          columns={footer.columns}
          visit={footer.visit}
          bottomLinks={footer.bottomLinks}
          copyright={brand.copyright}
        />
      </Block>
      <BagDrawer />
    </div>
  );
}

export default function App() {
  return (
    <BagProvider>
      <Shell />
    </BagProvider>
  );
}
