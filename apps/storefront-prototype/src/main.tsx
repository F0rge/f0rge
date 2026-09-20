// Throwaway storefront directions on /prototype?variant=A|B|C|D. D extends the Gallery with a bespoke material story.
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Button as B,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  Input,
  Stepper,
  UiProvider,
} from "@f0rge/ui";
import { TextInput } from "@f0rge/ui/forms";
import {
  ArrowUpRight,
  ArrowRight,
  Search,
  ShoppingBag,
  Heart,
  UserRound,
  Menu,
  X,
  Plus,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  Truck,
  ShieldCheck,
  Leaf,
  Ruler,
  ZoomIn,
  MapPin,
  Mail,
  Layers,
} from "lucide-react";
import {
  products,
  img,
  money,
  heroSlides,
  variantNames,
  type Product,
} from "./data";
import {
  Checkout,
  Account,
  type CartLine,
  type Order,
  type Address,
} from "./purchase";
import { ScrollPiece } from "./scroll-piece";
import "./styles.css";
import "./collector.css";

type Panel =
  | "bag"
  | "search"
  | "saved"
  | "menu"
  | "login"
  | "help"
  | "newsletter"
  | "zoom"
  | null;
type Route = { view: string; product?: string };
const collectorPalettes = [
  "Oxblood / citron",
  "Ultramarine / shell",
  "Forest / bone",
  "Terracotta / chalk",
  "Ink / saffron",
  "Aubergine / blush",
  "Cobalt / ice",
  "Moss / sand",
  "Charcoal / copper",
  "Petrol / stone",
];
const readRoute = (): Route => {
  const q = new URLSearchParams(location.search);
  const view = q.get("view") || "home";
  return {
    view: [
      "home",
      "shop",
      "product",
      "checkout",
      "account",
      "about",
      "journal",
    ].includes(view)
      ? view
      : "home",
    product: q.get("product") || undefined,
  };
};
const readVariant = () =>
  Math.max(
    0,
    ["A", "B", "C", "D"].indexOf(
      new URLSearchParams(location.search).get("variant") || "A",
    ),
  );
const readPalette = () => {
  const selected = Number(new URLSearchParams(location.search).get("palette"));
  return Number.isInteger(selected) &&
    selected >= 1 &&
    selected <= collectorPalettes.length
    ? selected - 1
    : 0;
};

function App() {
  const [route, setRoute] = useState(readRoute);
  const [variant, setVariant] = useState(readVariant);
  const [palette, setPalette] = useState(readPalette);
  const [panel, setPanel] = useState<Panel>(null);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [saved, setSaved] = useState<string[]>([]);
  const [category, setCategory] = useState("All furniture");
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState("");
  const [slide, setSlide] = useState(0);
  const [identity, setIdentity] = useState("");
  const [email, setEmail] = useState("");
  const [loginSent, setLoginSent] = useState(false);
  const [orders, setOrders] = useState<Order[]>([]);
  const [addresses, setAddresses] = useState<Record<string, Address>>({});
  const [consent, setConsent] = useState<string | null>(null);
  const [helpTopic, setHelpTopic] = useState("Here to help");
  const [zoomImage, setZoomImage] = useState("");
  const [newsletterDone, setNewsletterDone] = useState(false);
  useEffect(() => {
    document.body.dataset.design = ["A", "B", "C", "D"][variant];
    document.body.dataset.palette = String(palette + 1);
    return () => {
      delete document.body.dataset.design;
      delete document.body.dataset.palette;
    };
  }, [variant, palette]);
  const count = cart.reduce((n, item) => n + item.quantity, 0);
  const total = cart.reduce((n, item) => n + item.quantity * item.price, 0);
  const go = (view: string, product?: string) => {
    const url = new URL(location.href);
    url.hash = "";
    url.searchParams.set("view", view);
    product
      ? url.searchParams.set("product", product)
      : url.searchParams.delete("product");
    history.pushState({}, "", url);
    setRoute({ view, product });
    setPanel(null);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  const changeVariant = (next: number) => {
    const value = (next + variantNames.length) % variantNames.length;
    setVariant(value);
    const url = new URL(location.href);
    url.hash = "";
    if (route.view === "home") window.scrollTo({ top: 0, behavior: "instant" });
    url.searchParams.set("variant", ["A", "B", "C", "D"][value]);
    history.replaceState({}, "", url);
    console.info("Storefront prototype state", {
      variant: variantNames[value],
      route,
      cart,
      saved,
      authenticated: !!identity,
      consent,
    });
  };
  const changePalette = (next: number) => {
    const value = (next + collectorPalettes.length) % collectorPalettes.length;
    setPalette(value);
    const url = new URL(location.href);
    url.searchParams.set("palette", String(value + 1));
    history.replaceState({}, "", url);
    console.info("Storefront prototype state", {
      variant: "The Collector",
      palette: collectorPalettes[value],
    });
  };
  useEffect(() => {
    const onPop = () => {
      setRoute(readRoute());
      setVariant(readVariant());
      setPalette(readPalette());
      setPanel(null);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(id);
  }, [toast]);
  useEffect(() => {
    const keys = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest(
          'input,textarea,select,button,a,[contenteditable], [role="dialog"]',
        ) ||
        panel ||
        route.view !== "home"
      )
        return;
      if (event.key === "ArrowRight") changeVariant(variant + 1);
      if (event.key === "ArrowLeft") changeVariant(variant - 1);
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [variant, panel, route.view, cart, saved, identity, consent]);
  const shop = (cat = "All furniture") => {
    setCategory(cat);
    setQuery("");
    go("shop");
  };
  const toggleSaved = (id: string) => {
    setSaved((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };
  const add = (product: Product, finish: number, quantity: number) => {
    const key = product.id + "-" + finish;
    const already = cart.find((x) => x.key === key)?.quantity || 0;
    if (already + quantity > product.stock) {
      setToast(`Only ${product.stock} pieces are available in this finish.`);
      return;
    }
    setCart((prev) =>
      already
        ? prev.map((x) =>
            x.key === key ? { ...x, quantity: x.quantity + quantity } : x,
          )
        : [
            ...prev,
            {
              key,
              productId: product.id,
              finish,
              quantity,
              price: product.price + product.finishes[finish].extra,
            },
          ],
    );
    setPanel("bag");
  };
  const help = (topic: string) => {
    setHelpTopic(topic);
    setPanel("help");
  };
  const hero = heroSlides[slide];
  const product = products.find((p) => p.id === route.product) || products[0];
  const card = (p: Product) => (
    <ProductCard
      key={p.id}
      product={p}
      saved={saved.includes(p.id)}
      onSave={() => toggleSaved(p.id)}
      onOpen={() => go("product", p.id)}
    />
  );
  const filteredSearch = products.filter((p) =>
    `${p.name} ${p.type} ${p.category} ${p.material}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );

  return (
    <div className={`store variant-${["a", "b", "c", "d"][variant]}`}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="announcement">
        <span>Considered pieces. Collected for life.</span>
        <span>
          South Africa · ZAR <ChevronDown size={10} />
        </span>
      </div>
      <header className="site-header">
        <div className="header-left">
          <B
            className="icon-btn mobile-menu"
            aria-label="Open menu"
            onClick={() => setPanel("menu")}
          >
            <Menu />
          </B>
          <B className="wordmark" variant="ghost" onClick={() => go("home")}>
            VELLANO<span className="wordmark-dot">®</span>
          </B>
        </div>
        <nav aria-label="Main navigation">
          <B
            className={route.view === "shop" ? "nav-link active" : "nav-link"}
            onClick={() => shop()}
          >
            Furniture <ChevronDown size={12} />
          </B>
          <B
            className="nav-link"
            onClick={() => {
              go("home");
              setTimeout(
                () =>
                  document
                    .getElementById("rooms")
                    ?.scrollIntoView({ behavior: "smooth" }),
                50,
              );
            }}
          >
            The collections
          </B>
          <B className="nav-link" onClick={() => go("journal")}>
            Journal
          </B>
          <B className="nav-link" onClick={() => go("about")}>
            Our story
          </B>
        </nav>
        <div className="header-actions">
          <B
            className="icon-btn"
            aria-label="Search furniture"
            onClick={() => {
              setQuery("");
              setPanel("search");
            }}
          >
            <Search />
          </B>
          <B
            className="icon-btn saved-nav"
            aria-label={`Saved pieces, ${saved.length}`}
            onClick={() => setPanel("saved")}
          >
            <Heart />
            <span className={saved.length ? "tiny-count" : "hidden"}>
              {saved.length}
            </span>
          </B>
          <B
            className="icon-btn account-nav"
            aria-label="Your account"
            onClick={() => (identity ? go("account") : setPanel("login"))}
          >
            <UserRound />
          </B>
          <B
            className="bag-link"
            aria-label={`Open bag, ${count} items`}
            onClick={() => setPanel("bag")}
          >
            <ShoppingBag />
            <span>Bag</span>
            <span className="bag-count">{count}</span>
          </B>
        </div>
      </header>

      <main id="main">
        {route.view === "home" && (
          <>
            {variant === 0 && (
              <section className="hero-editorial">
                <img
                  key={hero.image}
                  className="hero-img"
                  src={img(hero.image)}
                  alt="A considered living space with linen seating and warm natural timber"
                />
                <div className="hero-shade" />
                <div className="hero-copy">
                  <span className="eyebrow">{hero.label}</span>
                  <h1>
                    {hero.title[0]}
                    <br />
                    <em>{hero.title[1]}</em>
                  </h1>
                  <p>
                    Furniture with feeling. For spaces that are entirely you.
                  </p>
                  <B className="btn cream" onClick={() => shop()}>
                    Discover the collection <ArrowUpRight size={17} />
                  </B>
                </div>
                <B
                  className="hotspot"
                  aria-label="Explore the featured piece"
                  onClick={() => go("product", hero.product)}
                >
                  <Plus size={21} />
                </B>
                <div className="hero-caption">
                  <span>{hero.caption}</span>
                  <B
                    className="text-white-link"
                    onClick={() => go("product", hero.product)}
                  >
                    Explore the piece <ArrowUpRight size={14} />
                  </B>
                </div>
                <div className="hero-pager">
                  <span>
                    0{slide + 1}
                    <span className="dim"> / 03</span>
                  </span>
                  <B
                    className="round-outline"
                    aria-label="Previous collection"
                    onClick={() => setSlide((slide + 2) % 3)}
                  >
                    <ChevronLeft size={17} />
                  </B>
                  <B
                    className="round-outline"
                    aria-label="Next collection"
                    onClick={() => setSlide((slide + 1) % 3)}
                  >
                    <ChevronRight size={17} />
                  </B>
                </div>
                <span className="vertical-note">
                  COMPOSED FOR EVERYDAY LIVING
                </span>
              </section>
            )}
            {variant === 1 && (
              <section className="hero-atelier">
                <div className="atelier-copy">
                  <span className="eyebrow">THE VELLANO EDIT · VOL. 01</span>
                  <h1>
                    Objects of
                    <br />
                    <em>quiet character.</em>
                  </h1>
                  <p>
                    Natural materials. Thoughtful proportions.
                    <br />
                    Furniture that finds its place in your life.
                  </p>
                  <B className="btn dark" onClick={() => shop()}>
                    Explore our furniture <ArrowUpRight size={17} />
                  </B>
                  <div className="atelier-footnote">
                    <span>01 — THE LIVING ROOM</span>
                    <span>Collected, never ordinary.</span>
                  </div>
                </div>
                <div className="atelier-visual">
                  <img
                    src={img("modular-cloud")}
                    alt="Light-filled room with a linen chaise sofa"
                  />
                  <B
                    className="floating-product"
                    onClick={() => go("product", "forma")}
                  >
                    <span>
                      Forma chaise sofa<small>Oat linen · {money(36900)}</small>
                    </span>
                    <ArrowUpRight />
                  </B>
                </div>
              </section>
            )}
            {(variant === 2 || variant === 3) && (
              <section className="hero-gallery">
                <div className="gallery-top">
                  <span className="eyebrow">
                    {variant === 3 ? (
                      <>
                        SOUTH AFRICA / VOL. 04
                        <br />
                        THE COLLECTOR’S EDIT
                      </>
                    ) : (
                      "A COLLECTION OF POSSIBILITIES"
                    )}
                  </span>
                  <h1>
                    {variant === 3 ? (
                      <>
                        A life less
                        <br />
                        <em>ordinary.</em>
                      </>
                    ) : (
                      <>
                        Make room
                        <br />
                        for <em>the exceptional.</em>
                      </>
                    )}
                  </h1>
                  <B className="gallery-cta" onClick={() => shop()}>
                    {variant === 3
                      ? "Find your point of view"
                      : "Enter the collection"}{" "}
                    <ArrowUpRight />
                  </B>
                </div>
                <div className="gallery-triptych">
                  {[products[1], products[0], products[2]].map((p, i) => (
                    <B
                      className={`gallery-piece gallery-piece-${i}`}
                      key={p.id}
                      onClick={() => go("product", p.id)}
                    >
                      <img src={img(p.image)} alt={p.type} />
                      <div>
                        <span>
                          {variant === 3 ? (
                            <>
                              <small>OBJECT / 0{i + 1}</small>
                              {p.name} <em>{p.type}</em>
                            </>
                          ) : (
                            <>
                              0{i + 1} / {p.name}
                            </>
                          )}
                        </span>
                        <ArrowUpRight size={20} />
                      </div>
                    </B>
                  ))}
                </div>
                {variant === 3 && (
                  <div className="collector-signoff">
                    <span>GOOD DESIGN SHOULD HAVE SOMETHING TO SAY.</span>
                    <span>YOURS SHOULD SAY SOMETHING ABOUT YOU.</span>
                    <a href="#sola-study">A closer look ↓</a>
                  </div>
                )}
              </section>
            )}

            <div className="reassurance">
              <span>
                <Leaf />
                Materials with character
              </span>
              <span>
                <Truck />
                Delivered with care
              </span>
              <span>
                <ShieldCheck />
                Considered, down to the detail
              </span>
            </div>
            {variant === 3 && <ScrollPiece onExplore={() => shop("Chairs")} />}
            <section className="collection-section wrap" id="collection">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">THE CONSIDERED COLLECTION</span>
                  <h2>Pieces to come home to.</h2>
                </div>
                <B className="text-link" onClick={() => shop()}>
                  View all furniture <ArrowUpRight size={16} />
                </B>
              </div>
              <div className="category-tabs">
                {["All furniture", "Sofas", "Chairs", "Tables", "Lighting"].map(
                  (cat) => (
                    <B
                      key={cat}
                      className={
                        category === cat
                          ? "category-tab selected"
                          : "category-tab"
                      }
                      onClick={() => setCategory(cat)}
                    >
                      {cat}
                    </B>
                  ),
                )}
              </div>
              <div className="product-grid">
                {products
                  .filter(
                    (p) =>
                      category === "All furniture" || p.category === category,
                  )
                  .slice(0, 4)
                  .map(card)}
              </div>
            </section>

            <section className="room-section" id="rooms">
              <div className="room-photo">
                <img
                  src={img("outdoor-teak")}
                  alt="A warm living room with leather sofa and natural wood table"
                />
                <B
                  className="room-hotspot one"
                  aria-label="Shop the Oslo sofa"
                  onClick={() => go("product", "oslo")}
                >
                  <Plus />
                </B>
                <B
                  className="room-hotspot two"
                  aria-label="Shop occasional chairs"
                  onClick={() => shop("Chairs")}
                >
                  <Plus />
                </B>
                <span className="image-credit">THE LIVING EDIT / 01</span>
              </div>
              <div className="room-copy">
                <span className="eyebrow">A ROOM, REIMAGINED</span>
                <h2>
                  Warmth is <br />
                  in the <em>details.</em>
                </h2>
                <p>
                  A little texture. A softer silhouette. The warmth of timber in
                  afternoon light. Build a room that feels like you, one
                  considered piece at a time.
                </p>
                <B className="text-link" onClick={() => shop()}>
                  Explore the living edit <ArrowUpRight size={17} />
                </B>
                <div className="room-samples">
                  <span style={{ background: "#bc8a5e" }} />
                  <span style={{ background: "#dfd7c5" }} />
                  <span style={{ background: "#7d806a" }} />
                  <small>Natural tones. Lasting character.</small>
                </div>
              </div>
            </section>

            <section className="philosophy wrap">
              <span className="eyebrow">THE VELLANO WAY</span>
              <h2>
                Less, but <em>more meaningful.</em>
              </h2>
              <p>
                We believe a beautiful home is built slowly.
                <br />
                With pieces you connect with. Materials you can feel.
                <br />
                And design that stays with you.
              </p>
              <B className="text-link" onClick={() => go("about")}>
                A little about us <ArrowUpRight size={16} />
              </B>
            </section>
            <section className="journal-section wrap">
              <div className="section-heading">
                <div>
                  <span className="eyebrow">NOTES ON LIVING</span>
                  <h2>The journal.</h2>
                </div>
                <B className="text-link" onClick={() => go("journal")}>
                  All stories <ArrowUpRight size={16} />
                </B>
              </div>
              <div className="journal-grid">
                {[
                  {
                    img: "walnut-lounge",
                    tag: "THE ART OF HOME",
                    title: "The beauty of a slower space.",
                  },
                  {
                    img: "marble-coffee",
                    tag: "MATERIAL MATTERS",
                    title: "Honest materials. Lasting feeling.",
                  },
                  {
                    img: "bi-dining-01",
                    tag: "GATHERED TOGETHER",
                    title: "A seat for every story.",
                  },
                ].map((a, i) => (
                  <B
                    key={a.title}
                    className="journal-card"
                    onClick={() => go("journal", String(i))}
                  >
                    <div className="journal-image">
                      <img src={img(a.img)} alt={a.title} />
                      <span>
                        <ArrowUpRight />
                      </span>
                    </div>
                    <span className="eyebrow">{a.tag} · 4 MIN READ</span>
                    <h3>{a.title}</h3>
                  </B>
                ))}
              </div>
            </section>
          </>
        )}

        {route.view === "shop" && (
          <Shop
            products={products}
            category={category}
            setCategory={setCategory}
            query={query}
            setQuery={setQuery}
            card={card}
          />
        )}
        {route.view === "product" &&
          !products.some((p) => p.id === route.product) && (
            <section className="empty-state checkout-empty">
              <h1>This piece isn’t in our collection.</h1>
              <B className="btn dark" onClick={() => shop()}>
                Explore furniture <ArrowRight size={17} />
              </B>
            </section>
          )}
        {route.view === "product" &&
          products.some((p) => p.id === route.product) && (
            <ProductDetail
              key={product.id}
              product={product}
              saved={saved.includes(product.id)}
              onSave={() => toggleSaved(product.id)}
              add={add}
              shop={shop}
              onZoom={(name) => {
                setZoomImage(name);
                setPanel("zoom");
              }}
              help={help}
              card={card}
            />
          )}
        {route.view === "checkout" && (
          <Checkout
            cart={cart}
            total={total}
            identity={identity}
            savedAddress={addresses[identity.toLowerCase()]}
            onLogin={() => setPanel("login")}
            onBack={() => setPanel("bag")}
            onShop={() => shop()}
            onComplete={(order) => {
              setOrders((prev) => [order, ...prev]);
              setCart([]);
            }}
          />
        )}
        {route.view === "account" && !identity && (
          <section className="empty-state account-page wrap">
            <UserRound size={34} />
            <h1>Make yourself at home.</h1>
            <p>Sign in to see your orders and saved addresses.</p>
            <B className="btn dark" onClick={() => setPanel("login")}>
              Sign in with email <ArrowRight size={17} />
            </B>
          </section>
        )}
        {route.view === "account" && identity && (
          <Account
            identity={identity}
            orders={orders.filter(
              (order) => order.email.toLowerCase() === identity.toLowerCase(),
            )}
            address={addresses[identity.toLowerCase()] || null}
            setAddress={(address) =>
              setAddresses((prev) => ({
                ...prev,
                [identity.toLowerCase()]: address,
              }))
            }
            onShop={() => shop()}
            onLogout={() => {
              setIdentity("");
              setLoginSent(false);
              go("home");
              setToast("You have been signed out.");
            }}
          />
        )}
        {(route.view === "about" || route.view === "journal") && (
          <StoryPage
            about={route.view === "about"}
            article={route.product}
            shop={shop}
          />
        )}
      </main>

      <section className="newsletter">
        <div>
          <span className="eyebrow">A NOTE FROM VELLANO</span>
          <h2>
            A little inspiration.
            <br />
            <em>Every now and then.</em>
          </h2>
        </div>
        <div className="newsletter-right">
          <p>New collections, considered spaces and stories worth sharing.</p>
          <B
            className="newsletter-trigger"
            onClick={() => setPanel("newsletter")}
          >
            <span>Your email address</span>
            <ArrowRight size={21} />
          </B>
          <small>A thoughtful inbox. Always.</small>
        </div>
      </section>
      <footer>
        <div className="footer-main">
          <div className="footer-brand">
            <span className="wordmark">VELLANO</span>
            <p>Furniture for a considered life.</p>
            <span className="footer-location">South Africa, with love.</span>
          </div>
          <div>
            <h4>Explore</h4>
            {["All furniture", "Sofas", "Chairs", "Tables", "Lighting"].map(
              (x) => (
                <B key={x} className="footer-link" onClick={() => shop(x)}>
                  {x}
                </B>
              ),
            )}
          </div>
          <div>
            <h4>Here to help</h4>
            {["Delivery & collection", "Returns & care", "Contact us"].map(
              (x) => (
                <B key={x} className="footer-link" onClick={() => help(x)}>
                  {x}
                </B>
              ),
            )}
            <B
              className="footer-link"
              onClick={() => (identity ? go("account") : setPanel("login"))}
            >
              Your account
            </B>
          </div>
          <div>
            <h4>A little more</h4>
            <B className="footer-link" onClick={() => go("about")}>
              Our story
            </B>
            <B className="footer-link" onClick={() => go("journal")}>
              The journal
            </B>
            <B
              className="footer-link"
              onClick={() => help("Privacy & cookies")}
            >
              Privacy & cookies
            </B>
          </div>
        </div>
        <div className="footer-bottom">
          <span>© 2026 Vellano. A considered life.</span>
          <span>ZAR · Prices include VAT</span>
          <span>
            VISA &nbsp; Mastercard &nbsp;{" "}
            <span className="peach-word">peach</span>
          </span>
        </div>
      </footer>

      <Dialog
        open={panel !== null}
        onOpenChange={(open) => {
          if (!open) setPanel(null);
        }}
      >
        <DialogContent
          showCloseButton={false}
          className={`panel ${panel === "zoom" ? "zoom-panel" : panel === "login" || panel === "newsletter" || panel === "help" ? "center-panel" : "drawer"}`}
        >
          <div className="panel-header">
            <DialogTitle>
              {panel === "bag"
                ? "Your bag"
                : panel === "search"
                  ? "Find your next favourite"
                  : panel === "saved"
                    ? "Your considered collection"
                    : panel === "menu"
                      ? "Explore Vellano"
                      : panel === "login"
                        ? "Welcome home."
                        : panel === "newsletter"
                          ? "Stay a little closer."
                          : panel === "zoom"
                            ? "A closer look"
                            : helpTopic}
            </DialogTitle>
            <B
              className="icon-btn"
              aria-label="Close panel"
              onClick={() => setPanel(null)}
            >
              <X />
            </B>
          </div>
          <DialogDescription className="sr-only">
            {panel === "bag"
              ? "Review your pieces and continue to checkout"
              : "Vellano interactive storefront panel"}
          </DialogDescription>
          {panel === "bag" && (
            <>
              <div className="panel-scroll">
                {!cart.length ? (
                  <div className="empty-state">
                    <ShoppingBag size={36} />
                    <h3>A little room for something beautiful.</h3>
                    <p>Your bag is empty. Find a piece that feels like home.</p>
                    <B className="btn dark" onClick={() => shop()}>
                      Explore the collection <ArrowRight size={17} />
                    </B>
                  </div>
                ) : (
                  <>
                    <p className="muted">
                      {count} considered {count === 1 ? "piece" : "pieces"},
                      ready for your home.
                    </p>
                    {cart.map((line) => {
                      const p = products.find((x) => x.id === line.productId)!;
                      return (
                        <div className="bag-item" key={line.key}>
                          <B
                            className="bag-image"
                            onClick={() => go("product", p.id)}
                          >
                            <img src={img(p.image)} alt={p.type} />
                          </B>
                          <div className="bag-item-body">
                            <div className="between">
                              <h3>{p.name}</h3>
                              <B
                                className="icon-btn small"
                                aria-label={`Remove ${p.name}`}
                                onClick={() =>
                                  setCart(
                                    cart.filter((x) => x.key !== line.key),
                                  )
                                }
                              >
                                <X size={16} />
                              </B>
                            </div>
                            <p>{p.type}</p>
                            <small>{p.finishes[line.finish].name}</small>
                            <div className="between bag-quantity">
                              <Stepper
                                size="compact"
                                label={p.name + " quantity"}
                                min={1}
                                max={p.stock}
                                value={line.quantity}
                                onChange={(quantity) =>
                                  setCart(
                                    cart.map((x) =>
                                      x.key === line.key
                                        ? { ...x, quantity }
                                        : x,
                                    ),
                                  )
                                }
                              />
                              <span>{money(line.price * line.quantity)}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    <div className="bag-note">
                      <Truck size={19} />
                      <span>
                        Delivered with care, or collect at your convenience.
                        <br />
                        <small>Choose at checkout.</small>
                      </span>
                    </div>
                  </>
                )}
              </div>
              {cart.length > 0 && (
                <div className="bag-total">
                  <div className="between">
                    <span>Subtotal</span>
                    <strong>{money(total)}</strong>
                  </div>
                  <p>Includes VAT. Delivery calculated at checkout.</p>
                  <B className="btn dark full" onClick={() => go("checkout")}>
                    Continue to checkout <ArrowRight size={18} />
                  </B>
                  <B
                    className="text-link center"
                    onClick={() => setPanel(null)}
                  >
                    Continue exploring
                  </B>
                  <div className="secure-note">
                    <ShieldCheck size={14} /> Secure payment with Peach
                  </div>
                </div>
              )}
            </>
          )}
          {panel === "search" && (
            <div className="panel-scroll">
              <div className="search-box">
                <Search size={21} />
                <Input
                  autoFocus
                  aria-label="Search furniture"
                  placeholder="Try ‘sofa’, ‘oak’ or ‘linen’"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <B
                    className="icon-btn"
                    aria-label="Clear search"
                    onClick={() => setQuery("")}
                  >
                    <X size={15} />
                  </B>
                )}
              </div>
              <span className="eyebrow">
                {query
                  ? `${filteredSearch.length} ${filteredSearch.length === 1 ? "PIECE" : "PIECES"} FOUND`
                  : "A FEW PLACES TO START"}
              </span>
              {filteredSearch.length ? (
                filteredSearch.map((p) => (
                  <B
                    key={p.id}
                    className="search-result"
                    onClick={() => go("product", p.id)}
                  >
                    <img src={img(p.image)} alt="" />
                    <span>
                      <strong>{p.name}</strong>
                      <small>
                        {p.type} · {p.material.split(" · ")[0]}
                      </small>
                      <span>{money(p.price)}</span>
                    </span>
                    <ArrowUpRight size={19} />
                  </B>
                ))
              ) : (
                <div className="empty-state">
                  <h3>No pieces found.</h3>
                  <p>Try a material, category or a shorter search.</p>
                  <B className="text-link" onClick={() => setQuery("")}>
                    Clear search <ArrowRight size={16} />
                  </B>
                </div>
              )}
            </div>
          )}
          {panel === "saved" && (
            <div className="panel-scroll">
              {saved.length ? (
                <>
                  <p className="muted">A few favourites to keep in mind.</p>
                  <div className="saved-grid">
                    {products.filter((p) => saved.includes(p.id)).map(card)}
                  </div>
                </>
              ) : (
                <div className="empty-state">
                  <Heart size={36} />
                  <h3>Keep the pieces you love close.</h3>
                  <p>Tap the heart on a piece to start your collection.</p>
                  <B className="btn dark" onClick={() => shop()}>
                    Find your favourites <ArrowRight size={17} />
                  </B>
                </div>
              )}
            </div>
          )}
          {panel === "menu" && (
            <div className="menu-content">
              {["All furniture", "Sofas", "Chairs", "Tables", "Lighting"].map(
                (x) => (
                  <B key={x} onClick={() => shop(x)}>
                    {x}
                    <ArrowUpRight />
                  </B>
                ),
              )}
              <hr />
              <B onClick={() => go("journal")}>
                The journal
                <ArrowUpRight />
              </B>
              <B onClick={() => (identity ? go("account") : setPanel("login"))}>
                Your account
                <UserRound />
              </B>
              <B onClick={() => setPanel("saved")}>
                Saved pieces
                <Heart />
              </B>
            </div>
          )}
          {panel === "login" && (
            <div className="auth-content">
              <span className="eyebrow">YOUR VELLANO</span>
              <h3>
                {loginSent
                  ? "A little closer to home."
                  : "Your favourites. Your orders. Your space."}
              </h3>
              <p>
                {loginSent
                  ? "In the live store, a secure sign-in link will arrive in your inbox. No password to remember."
                  : "Sign in with your email to keep track of your orders and save your details for next time."}
              </p>
              {!loginSent ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setLoginSent(true);
                  }}
                >
                  <TextInput
                    required
                    type="email"
                    label="Email address"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <B className="btn dark full" type="submit">
                    Email me a sign-in link <ArrowRight size={17} />
                  </B>
                  <small className="demo-note">
                    Prototype: no email is sent. Use a sample address.
                  </small>
                </form>
              ) : (
                <>
                  <div className="mail-circle">
                    <Mail />
                  </div>
                  <p className="muted">Link preview for {email}</p>
                  <B
                    className="btn dark full"
                    onClick={() => {
                      setIdentity(email);
                      if (route.view === "checkout" && cart.length) {
                        setPanel(null);
                      } else {
                        go("account");
                      }
                      setToast("Welcome to your Vellano.");
                    }}
                  >
                    Preview signed-in account <ArrowRight size={17} />
                  </B>
                  <B
                    className="text-link center"
                    onClick={() => setLoginSent(false)}
                  >
                    Use a different email
                  </B>
                </>
              )}
            </div>
          )}
          {panel === "newsletter" && (
            <div className="auth-content">
              {newsletterDone ? (
                <>
                  <Check size={38} />
                  <h3>You’re on the list.</h3>
                  <p>
                    In the live store, thoughtful inspiration will find its way
                    to your inbox.
                  </p>
                  <B className="btn dark full" onClick={() => setPanel(null)}>
                    Keep exploring <ArrowRight size={17} />
                  </B>
                </>
              ) : (
                <>
                  <p>
                    A first look at new pieces, beautiful spaces and notes on
                    considered living.
                  </p>
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      setNewsletterDone(true);
                    }}
                  >
                    <TextInput
                      required
                      type="email"
                      label="Your email address"
                      placeholder="you@example.com"
                    />
                    <B className="btn dark full" type="submit">
                      A little inspiration, please <ArrowRight size={17} />
                    </B>
                    <small className="demo-note">
                      Preview only. No subscription is created.
                    </small>
                  </form>
                </>
              )}
            </div>
          )}
          {panel === "help" && (
            <div className="help-content">
              {helpTopic === "Privacy & cookies" ? (
                <>
                  <h3>Your space. Your choice.</h3>
                  <p>
                    Essential functions keep your bag and checkout working.
                    Optional analytics help us understand how our collection is
                    explored.
                  </p>
                  <p>
                    This prototype sends no analytics and keeps all choices in
                    memory.
                  </p>
                  <B
                    className="btn dark full"
                    onClick={() => {
                      setConsent("accepted");
                      setPanel(null);
                      setToast("Analytics preference: accepted (preview).");
                    }}
                  >
                    Allow optional analytics
                  </B>
                  <B
                    className="btn outline full"
                    onClick={() => {
                      setConsent("essential");
                      setPanel(null);
                      setToast("Only essential functions selected.");
                    }}
                  >
                    Essential only
                  </B>
                </>
              ) : (
                <>
                  <span className="eyebrow">THOUGHTFUL SERVICE</span>
                  <h3>
                    {helpTopic === "Delivery & collection"
                      ? "The last step should feel easy."
                      : helpTopic === "Returns & care"
                        ? "Beautiful for the long run."
                        : "A little guidance goes a long way."}
                  </h3>
                  <p>
                    {helpTopic === "Delivery & collection"
                      ? "Choose domestic delivery or complimentary collection at checkout. We’ll confirm a suitable date before your pieces leave us."
                      : helpTopic === "Returns & care"
                        ? "Need help with a piece? Contact our team with your order number. We’ll help you understand your options and how to care for your furniture."
                        : "From choosing the right finish to checking a doorway, our team will help you feel confident in your choice."}
                  </p>
                  <div className="service-row">
                    <Truck />
                    <div>
                      <strong>Delivery, thoughtfully arranged</strong>
                      <p>Demo estimate: R 650 · 5–10 working days.</p>
                    </div>
                  </div>
                  <div className="service-row">
                    <MapPin />
                    <div>
                      <strong>Prefer to collect?</strong>
                      <p>
                        Complimentary collection in Gauteng, by arrangement.
                      </p>
                    </div>
                  </div>
                  <small className="demo-note">
                    Service details and delivery amounts are illustrative until
                    launch policies are finalised.
                  </small>
                </>
              )}
            </div>
          )}
          {panel === "zoom" && (
            <img
              className="zoom-photo"
              src={img(zoomImage)}
              alt="Furniture photograph, enlarged"
            />
          )}
        </DialogContent>
      </Dialog>
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
      {import.meta.env.DEV && (
        <div
          className="prototype-switcher"
          aria-label="Prototype design variations"
        >
          <span className="prototype-label">
            <Layers size={13} /> Design preview
          </span>
          <B
            className="switch-arrow"
            aria-label="Previous design"
            onClick={() => changeVariant(variant - 1)}
          >
            <ChevronLeft size={15} />
          </B>
          <span className="variant-title">
            {["A", "B", "C", "D"][variant]} · {variantNames[variant]}
          </span>
          <B
            className="switch-arrow"
            aria-label="Next design"
            onClick={() => changeVariant(variant + 1)}
          >
            <ChevronRight size={15} />
          </B>
          <span className="prototype-state">
            {count} in bag · {saved.length} saved
          </span>
        </div>
      )}
      {import.meta.env.DEV && variant === 3 && (
        <div
          className="collector-palette-switcher"
          aria-label="Collector typography and palette variations"
        >
          <span>Collector skins</span>
          <button
            type="button"
            className="collector-palette-arrow"
            aria-label="Previous Collector skin"
            onClick={() => changePalette(palette - 1)}
          >
            <ChevronLeft size={14} />
          </button>
          <span className="collector-palette-name">
            {palette + 1}/10 · {collectorPalettes[palette]}
          </span>
          <button
            type="button"
            className="collector-palette-arrow"
            aria-label="Next Collector skin"
            onClick={() => changePalette(palette + 1)}
          >
            <ChevronRight size={14} />
          </button>
          <div
            className="collector-palette-dots"
            aria-label="Choose a Collector skin"
          >
            {collectorPalettes.map((name, index) => (
              <button
                type="button"
                key={name}
                aria-label={`Skin ${index + 1}: ${name}`}
                aria-pressed={index === palette}
                className={`collector-palette-dot palette-dot-${index + 1}`}
                onClick={() => changePalette(index)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ProductCard({
  product: p,
  saved,
  onSave,
  onOpen,
}: {
  product: Product;
  saved: boolean;
  onSave: () => void;
  onOpen: () => void;
}) {
  return (
    <article className="product-card">
      <div className="product-photo">
        <B
          className="product-open"
          onClick={onOpen}
          aria-label={`View ${p.name} ${p.type}`}
        >
          <img
            loading="lazy"
            src={img(p.image)}
            alt={p.type}
            style={{ objectPosition: p.position }}
          />
          <span className="quick-view">
            Discover the piece <ArrowUpRight size={16} />
          </span>
        </B>
        {p.badge && <span className="product-badge">{p.badge}</span>}
        <B
          className={`save-button ${saved ? "is-saved" : ""}`}
          aria-label={`${saved ? "Unsave" : "Save"} ${p.name}`}
          aria-pressed={saved}
          onClick={onSave}
        >
          <Heart size={18} fill={saved ? "currentColor" : "none"} />
        </B>
      </div>
      <B className="product-title" onClick={onOpen}>
        <h3>{p.name}</h3>
        <span>{money(p.price)}</span>
      </B>
      <p>{p.type}</p>
      <div className="card-finishes">
        {p.finishes.map((f) => (
          <span key={f.name} title={f.name} style={{ background: f.color }} />
        ))}
        <small>{p.finishes.length} finishes</small>
      </div>
    </article>
  );
}

function Shop({
  products: items,
  category,
  setCategory,
  query,
  setQuery,
  card,
}: {
  products: Product[];
  category: string;
  setCategory: (v: string) => void;
  query: string;
  setQuery: (v: string) => void;
  card: (p: Product) => React.ReactNode;
}) {
  const [filters, setFilters] = useState(false),
    [inStock, setInStock] = useState(false),
    [budget, setBudget] = useState(50000),
    [sort, setSort] = useState("considered");
  const result = items
    .filter(
      (p) =>
        (category === "All furniture" || p.category === category) &&
        `${p.name} ${p.type} ${p.material}`
          .toLowerCase()
          .includes(query.toLowerCase()) &&
        (!inStock || p.stock > 0) &&
        p.price <= budget,
    )
    .sort((a, b) =>
      sort === "low"
        ? a.price - b.price
        : sort === "high"
          ? b.price - a.price
          : 0,
    );
  return (
    <section className="shop-page wrap">
      <div className="shop-intro">
        <span className="eyebrow">FURNITURE FOR A CONSIDERED LIFE</span>
        <h1>
          {query
            ? `A place for “${query}”.`
            : category === "All furniture"
              ? "Find your forever piece."
              : category + ". With character."}
        </h1>
        <p>
          Beautiful forms. Honest materials. A collection made to feel like
          home.
        </p>
      </div>
      <div className="shop-toolbar">
        <div className="category-tabs">
          {["All furniture", "Sofas", "Chairs", "Tables", "Lighting"].map(
            (cat) => (
              <B
                key={cat}
                className={
                  category === cat ? "category-tab selected" : "category-tab"
                }
                onClick={() => setCategory(cat)}
              >
                {cat}
              </B>
            ),
          )}
        </div>
        <div className="filter-actions">
          <B
            className={`filter-toggle ${filters ? "selected" : ""}`}
            aria-expanded={filters}
            onClick={() => setFilters(!filters)}
          >
            <SlidersHorizontal size={16} /> Filters{" "}
            {(inStock || budget < 50000) && <span className="filter-dot" />}
          </B>
          <label className="sort-label">
            <span className="sr-only">Sort furniture</span>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="considered">Our considered edit</option>
              <option value="low">Price: low to high</option>
              <option value="high">Price: high to low</option>
            </select>
          </label>
        </div>
      </div>
      {filters && (
        <div className="filter-panel">
          <TextInput
            label="Search the collection"
            placeholder="Name or material"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label className="budget-label">
            Up to {money(budget)}
            <input
              type="range"
              min="3000"
              max="50000"
              step="500"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={inStock}
              onChange={(e) => setInStock(e.target.checked)}
            />{" "}
            In-stock pieces only
          </label>
          <B
            className="text-link"
            onClick={() => {
              setInStock(false);
              setBudget(50000);
              setQuery("");
              setCategory("All furniture");
            }}
          >
            Reset filters
          </B>
        </div>
      )}
      <div className="results-meta">
        <span>
          {result.length} considered {result.length === 1 ? "piece" : "pieces"}
        </span>
        <span>Prices include VAT</span>
      </div>
      {result.length ? (
        <div className="product-grid">{result.map(card)}</div>
      ) : (
        <div className="empty-state">
          <h2>A little too considered?</h2>
          <p>Widen your filters to discover more of the collection.</p>
          <B
            className="btn dark"
            onClick={() => {
              setInStock(false);
              setBudget(50000);
              setQuery("");
              setCategory("All furniture");
            }}
          >
            Show all furniture <ArrowRight size={17} />
          </B>
        </div>
      )}
    </section>
  );
}

function ProductDetail({
  product: p,
  saved,
  onSave,
  add,
  shop,
  onZoom,
  help,
  card,
}: {
  product: Product;
  saved: boolean;
  onSave: () => void;
  add: (p: Product, f: number, q: number) => void;
  shop: (c?: string) => void;
  onZoom: (name: string) => void;
  help: (topic: string) => void;
  card: (p: Product) => React.ReactNode;
}) {
  const [finish, setFinish] = useState(0),
    [quantity, setQuantity] = useState(1),
    [gallery, setGallery] = useState(0),
    [dimensions, setDimensions] = useState(false);
  const images = [...new Set([p.image, p.scene])];
  return (
    <>
      <div className="breadcrumbs wrap">
        <B className="text-link" onClick={() => shop()}>
          Furniture
        </B>
        <span>/</span>
        <B className="text-link" onClick={() => shop(p.category)}>
          {p.category}
        </B>
        <span>/</span>
        <span>{p.name}</span>
      </div>
      <section className="product-detail wrap">
        <div className="product-gallery">
          <div className="detail-photo">
            <img
              src={img(images[gallery])}
              alt={`${p.name} ${gallery ? "in a considered room" : "furniture photograph"}`}
              style={{ objectPosition: p.position }}
            />
            <B
              className="zoom-button"
              aria-label="Enlarge product image"
              onClick={() => onZoom(images[gallery])}
            >
              <ZoomIn size={19} />
            </B>
            {dimensions && (
              <div className="dimension-overlay">
                <div>
                  <Ruler size={26} />
                  <h3>Made to fit your space.</h3>
                  <dl>
                    <div>
                      <dt>Width</dt>
                      <dd>{p.dimensions[0]} cm</dd>
                    </div>
                    <div>
                      <dt>Depth</dt>
                      <dd>{p.dimensions[1]} cm</dd>
                    </div>
                    <div>
                      <dt>Height</dt>
                      <dd>{p.dimensions[2]} cm</dd>
                    </div>
                  </dl>
                  <p>Remember to measure doorways and access routes.</p>
                </div>
              </div>
            )}
          </div>
          <div className="gallery-controls">
            <div className="thumbnails">
              {images.map((im, i) => (
                <B
                  className={gallery === i ? "thumb selected" : "thumb"}
                  key={i}
                  aria-label={i ? "Show room inspiration" : "Show product view"}
                  aria-pressed={gallery === i}
                  onClick={() => {
                    setGallery(i);
                    setDimensions(false);
                  }}
                >
                  <img src={img(im)} alt="" />
                </B>
              ))}
            </div>
            <B
              className="text-link"
              aria-pressed={dimensions}
              onClick={() => setDimensions(!dimensions)}
            >
              <Ruler size={16} />
              {dimensions ? "Hide dimensions" : "See dimensions"}
            </B>
          </div>
        </div>
        <div className="product-info">
          <span className="eyebrow">
            THE{" "}
            {p.category === "Sofas"
              ? "LIVING"
              : p.category === "Tables"
                ? "GATHERING"
                : "CONSIDERED"}{" "}
            COLLECTION
          </span>
          <div className="between">
            <h1>{p.name}</h1>
            <B
              className={`icon-btn large ${saved ? "is-saved" : ""}`}
              aria-label={`${saved ? "Unsave" : "Save"} ${p.name}`}
              aria-pressed={saved}
              onClick={onSave}
            >
              <Heart fill={saved ? "currentColor" : "none"} />
            </B>
          </div>
          <p className="product-subtitle">{p.type}</p>
          <div className="detail-price">
            {money(p.price + p.finishes[finish].extra)}
            <small>VAT included</small>
          </div>
          <p className="product-description">{p.description}</p>
          <div className="finish-picker">
            <div className="between">
              <span>
                Finish <strong>{p.finishes[finish].name}</strong>
              </span>
              <span className="muted">{p.finishes.length} options</span>
            </div>
            <div className="finish-options">
              {p.finishes.map((f, i) => (
                <B
                  key={f.name}
                  className={
                    finish === i ? "finish-swatch selected" : "finish-swatch"
                  }
                  style={{ background: f.color }}
                  aria-label={`Select ${f.name}`}
                  aria-pressed={finish === i}
                  onClick={() => setFinish(i)}
                >
                  {finish === i && <Check size={15} />}
                </B>
              ))}
            </div>
          </div>
          <p className={`stock-status ${p.stock ? "" : "unavailable"}`}>
            <span />
            {p.stock
              ? `In stock · ${p.stock} pieces available`
              : "Returning soon · Currently unavailable"}
          </p>
          <div className="purchase-row">
            <div className="detail-quantity">
              <Stepper
                size="compact"
                label="quantity"
                min={1}
                max={Math.max(1, p.stock)}
                value={quantity}
                onChange={setQuantity}
              />
            </div>
            <B
              className="btn dark full"
              disabled={!p.stock}
              onClick={() => add(p, finish, quantity)}
            >
              {p.stock ? "Add to bag" : "Currently unavailable"}
              <ArrowRight size={18} />
            </B>
          </div>
          <div className="product-delivery">
            <Truck size={18} />
            <span>
              Delivered with care in 5–10 working days.
              <br />
              <B
                className="text-link"
                onClick={() => help("Delivery & collection")}
              >
                Delivery & collection information
              </B>
            </span>
          </div>
          <div className="product-accordions">
            <details open>
              <summary>
                Materials & character <Plus size={16} />
              </summary>
              <p>
                {p.material}. Natural variation gives each piece its own
                character. Photography is illustrative of this design preview.
              </p>
            </details>
            <details>
              <summary>
                Dimensions & details <Plus size={16} />
              </summary>
              <p>
                W {p.dimensions[0]} × D {p.dimensions[1]} × H {p.dimensions[2]}{" "}
                cm.
              </p>
              <p>
                SKU: VEL-{p.id.toUpperCase()}-{finish + 1}. Measure your room
                and access routes before ordering.
              </p>
            </details>
            <details>
              <summary>
                Care for your piece <Plus size={16} />
              </summary>
              <p>
                Keep away from prolonged direct sunlight. Dust gently, blot
                spills promptly, and use a soft, dry cloth on timber. Avoid
                harsh cleaning products.
              </p>
            </details>
          </div>
        </div>
      </section>
      <section className="related wrap">
        <div className="section-heading">
          <div>
            <span className="eyebrow">BEAUTIFUL TOGETHER</span>
            <h2>A few kindred pieces.</h2>
          </div>
          <B className="text-link" onClick={() => shop()}>
            Explore the collection <ArrowUpRight size={16} />
          </B>
        </div>
        <div className="product-grid">
          {products
            .filter((x) => x.id !== p.id)
            .slice(0, 4)
            .map(card)}
        </div>
      </section>
    </>
  );
}

function StoryPage({
  about,
  article,
  shop,
}: {
  about: boolean;
  article?: string;
  shop: (c?: string) => void;
}) {
  const requested = Number(article || 0),
    a = Number.isInteger(requested) && requested >= 0 ? requested % 3 : 0,
    titles = [
      "The beauty of a slower space.",
      "Honest materials. Lasting feeling.",
      "A seat for every story.",
    ];
  return (
    <article className="story-page">
      <div className="story-heading wrap">
        <span className="eyebrow">
          {about ? "OUR STORY" : "THE VELLANO JOURNAL · NOTES ON LIVING"}
        </span>
        <h1>
          {about ? (
            <>
              Furniture with feeling.
              <br />
              <em>Spaces with soul.</em>
            </>
          ) : (
            titles[a % 3]
          )}
        </h1>
        <p>
          {about
            ? "We believe that the most beautiful homes are the ones that feel like you."
            : "A few thoughts on finding beauty in the everyday."}
        </p>
      </div>
      <img
        className="story-banner"
        src={img(
          about
            ? "bi-sofa-06"
            : ["walnut-lounge", "marble-coffee", "bi-dining-01"][a % 3],
        )}
        alt="A thoughtfully composed interior"
      />
      <div className="story-prose">
        <span className="eyebrow">
          {about ? "A CONSIDERED LIFE" : "SPACES TO LIVE IN, NOT JUST LOOK AT"}
        </span>
        <h2>
          {about
            ? "Collected, never ordinary."
            : "Start with how you want to feel."}
        </h2>
        <p>
          A home is more than the things we put in it. It is the light that
          falls across a favourite chair. The texture beneath your hand. The
          table that gathers the people you love.
        </p>
        <p>
          We are drawn to furniture that makes those everyday moments a little
          more beautiful. Honest materials, thoughtful proportions and quiet
          details that reveal themselves over time.
        </p>
        <h3>Room for your own story.</h3>
        <p>
          There is no single way to create a beautiful home. Mix a soft,
          generous sofa with a sculptural accent chair. Let the grain of natural
          wood sit beside a beautifully woven textile. Give each piece a little
          room to breathe.
        </p>
        <p>
          Our collection is a starting point. What you make of it is entirely
          your own.
        </p>
        <B className="btn dark" onClick={() => shop()}>
          Find a piece to begin with <ArrowUpRight size={17} />
        </B>
      </div>
    </article>
  );
}

createRoot(document.getElementById("root")!).render(
  <UiProvider>
    <App />
  </UiProvider>,
);
