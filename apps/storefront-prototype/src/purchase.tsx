import { useEffect, useState } from "react";
import {
  Button as B,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@f0rge/ui";
import { TextInput, Select } from "@f0rge/ui/forms";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ShieldCheck,
  Truck,
  MapPin,
  ShoppingBag,
  Package,
  Plus,
  X,
  ChevronDown,
  Mail,
} from "lucide-react";
import { products, img, money } from "./data";

export type CartLine = {
  key: string;
  productId: string;
  finish: number;
  quantity: number;
  price: number;
};
export type Order = {
  id: string;
  items: CartLine[];
  total: number;
  delivery: string;
  email: string;
  name: string;
  date: string;
};
export type Address = {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  street: string;
  city: string;
  postal: string;
  province: string;
};
const emptyAddress: Address = {
  firstName: "",
  lastName: "",
  email: "",
  phone: "",
  street: "",
  city: "",
  postal: "",
  province: "Gauteng",
};
const sampleAddress: Address = {
  firstName: "Alex",
  lastName: "Morgan",
  email: "alex@example.com",
  phone: "082 123 4567",
  street: "12 Oak Avenue",
  city: "Johannesburg",
  postal: "2196",
  province: "Gauteng",
};

export function Checkout({
  cart,
  total,
  identity,
  savedAddress,
  onLogin,
  onBack,
  onShop,
  onComplete,
}: {
  cart: CartLine[];
  total: number;
  identity: string;
  savedAddress?: Address;
  onLogin: () => void;
  onBack: () => void;
  onShop: () => void;
  onComplete: (o: Order) => void;
}) {
  const [step, setStep] = useState(0),
    [method, setMethod] = useState("delivery"),
    [address, setAddress] = useState<Address>({
      ...emptyAddress,
      ...savedAddress,
      email: identity,
    }),
    [payment, setPayment] = useState(false),
    [order, setOrder] = useState<Order | null>(null),
    [terms, setTerms] = useState(false);
  useEffect(() => {
    if (identity) setAddress((current) => ({ ...current, email: identity }));
  }, [identity]);
  const shipping = method === "delivery" ? 650 : 0;
  const field = (key: keyof Address, value: string) =>
    setAddress({ ...address, [key]: value });
  const complete = () => {
    const newOrder = {
      id: `VL-${String(1001 + Math.floor(Math.random() * 8999))}`,
      items: [...cart],
      total: total + shipping,
      delivery: method,
      email: address.email,
      name: address.firstName,
      date: new Date().toLocaleDateString("en-ZA"),
    };
    setOrder(newOrder);
    setPayment(false);
    onComplete(newOrder);
  };
  if (order)
    return (
      <section className="confirmation wrap">
        <div className="confirmation-mark">
          <Check size={34} />
        </div>
        <span className="eyebrow">ORDER {order.id} · PREVIEW</span>
        <h1>
          Something beautiful
          <br />
          is <em>on its way.</em>
        </h1>
        <p>Thank you, {order.name}. Your pieces have found their next home.</p>
        <div className="confirmation-details">
          <div>
            <Mail size={22} />
            <span>
              Order confirmation<small>{order.email}</small>
            </span>
          </div>
          <div>
            {order.delivery === "delivery" ? <Truck /> : <MapPin />}
            <span>
              {order.delivery === "delivery"
                ? "Delivered with care"
                : "Ready to collect soon"}
              <small>
                {order.delivery === "delivery"
                  ? "We’ll be in touch to arrange your delivery."
                  : "We’ll let you know when your pieces are ready."}
              </small>
            </span>
          </div>
          <div>
            <ShoppingBag />
            <span>
              {order.items.reduce((n, x) => n + x.quantity, 0)} considered{" "}
              {order.items.reduce((n, x) => n + x.quantity, 0) === 1
                ? "piece"
                : "pieces"}
              <small>{money(order.total)} · VAT included</small>
            </span>
          </div>
        </div>
        <B className="btn dark" onClick={onShop}>
          Keep exploring <ArrowRight size={17} />
        </B>
        {!identity && (
          <B className="text-link center" onClick={onLogin}>
            Create your passwordless account <ArrowRight size={16} />
          </B>
        )}
        <p className="demo-note">
          This was a simulated order. No payment was taken and no email was
          sent.
        </p>
      </section>
    );
  if (!cart.length)
    return (
      <div className="empty-state checkout-empty">
        <ShoppingBag size={38} />
        <h1>Your next favourite awaits.</h1>
        <p>Add a piece to your bag to begin.</p>
        <B className="btn dark" onClick={onShop}>
          Explore furniture <ArrowRight size={17} />
        </B>
      </div>
    );
  return (
    <section className="checkout-page wrap">
      <B className="text-link" onClick={onBack}>
        <ArrowLeft size={15} /> Back to your bag
      </B>
      <div className="checkout-heading">
        <div>
          <span className="eyebrow">THE LAST FEW DETAILS</span>
          <h1>Make yourself at home.</h1>
        </div>
        <span className="secure-note">
          <ShieldCheck size={17} /> Secure checkout
        </span>
      </div>
      <div className="checkout-grid">
        <div className="checkout-form">
          <div className="checkout-steps">
            {["Your details", "Delivery", "Review & pay"].map((label, i) => (
              <B
                key={label}
                className={
                  i === step
                    ? "checkout-step current"
                    : i < step
                      ? "checkout-step done"
                      : "checkout-step"
                }
                disabled={i > step}
                onClick={() => setStep(i)}
              >
                <span>{i < step ? <Check size={13} /> : i + 1}</span>
                {label}
              </B>
            ))}
          </div>
          {step === 0 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setStep(1);
              }}
            >
              <div className="between">
                <h2>Your details</h2>
                {!identity && (
                  <B className="text-link" onClick={onLogin}>
                    Already at home here? Sign in
                  </B>
                )}
              </div>
              <p className="muted">
                {identity
                  ? "Signed in. Your order will appear in your account."
                  : "Checkout as a guest. An account is always optional."}
              </p>
              <div className="field-grid">
                <TextInput
                  required
                  label="First name"
                  autoComplete="given-name"
                  value={address.firstName}
                  onChange={(e) => field("firstName", e.target.value)}
                />
                <TextInput
                  required
                  label="Last name"
                  autoComplete="family-name"
                  value={address.lastName}
                  onChange={(e) => field("lastName", e.target.value)}
                />
                <TextInput
                  className="span-2"
                  required
                  type="email"
                  label="Email address"
                  autoComplete="email"
                  value={address.email}
                  onChange={(e) => field("email", e.target.value)}
                  description="Your order updates will find you here."
                />
                <TextInput
                  className="span-2"
                  required
                  type="tel"
                  label="Mobile number"
                  autoComplete="tel"
                  value={address.phone}
                  onChange={(e) => field("phone", e.target.value)}
                  description="So we can arrange a smooth delivery."
                />
              </div>
              <div className="form-bottom">
                <B
                  className="text-link demo-fill"
                  onClick={() =>
                    setAddress({
                      ...sampleAddress,
                      email: identity || sampleAddress.email,
                    })
                  }
                >
                  Use example details
                </B>
                <B className="btn dark" type="submit">
                  Continue to delivery <ArrowRight size={17} />
                </B>
              </div>
            </form>
          )}
          {step === 1 && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setStep(2);
              }}
            >
              <h2>Coming to your home.</h2>
              <p className="muted">
                Choose the last part of your piece’s journey.
              </p>
              <div className="delivery-options">
                <B
                  className={
                    method === "delivery"
                      ? "delivery-option selected"
                      : "delivery-option"
                  }
                  aria-pressed={method === "delivery"}
                  onClick={() => setMethod("delivery")}
                >
                  <Truck size={23} />
                  <span>
                    <strong>Delivered with care</strong>
                    <small>5–10 working days · South Africa</small>
                  </span>
                  <span>{money(650)}</span>
                  <span className="radio-dot" />
                </B>
                <B
                  className={
                    method === "collection"
                      ? "delivery-option selected"
                      : "delivery-option"
                  }
                  aria-pressed={method === "collection"}
                  onClick={() => setMethod("collection")}
                >
                  <MapPin size={23} />
                  <span>
                    <strong>Collect your pieces</strong>
                    <small>By arrangement · Gauteng</small>
                  </span>
                  <span>Complimentary</span>
                  <span className="radio-dot" />
                </B>
              </div>
              {method === "delivery" ? (
                <div className="field-grid">
                  <TextInput
                    className="span-2"
                    required
                    label="Street address"
                    autoComplete="street-address"
                    value={address.street}
                    onChange={(e) => field("street", e.target.value)}
                  />
                  <TextInput
                    required
                    label="City / town"
                    autoComplete="address-level2"
                    value={address.city}
                    onChange={(e) => field("city", e.target.value)}
                  />
                  <TextInput
                    required
                    label="Postal code"
                    autoComplete="postal-code"
                    inputMode="numeric"
                    pattern="[0-9]{4}"
                    value={address.postal}
                    onChange={(e) => field("postal", e.target.value)}
                  />
                  <Select
                    label="Province"
                    className="span-2"
                    data={[
                      "Gauteng",
                      "Western Cape",
                      "KwaZulu-Natal",
                      "Eastern Cape",
                      "Free State",
                      "Limpopo",
                      "Mpumalanga",
                      "North West",
                      "Northern Cape",
                    ]}
                    value={address.province}
                    allowDeselect={false}
                    onChange={(v) => field("province", v || "Gauteng")}
                  />
                </div>
              ) : (
                <div className="collection-note">
                  <MapPin size={23} />
                  <h3>A personal handover.</h3>
                  <p>
                    We’ll confirm the collection address and arrange a time with
                    you once your pieces are ready.
                  </p>
                </div>
              )}
              <div className="form-bottom">
                <B className="text-link" onClick={() => setStep(0)}>
                  <ArrowLeft size={15} /> Your details
                </B>
                <B className="btn dark" type="submit">
                  Review your order <ArrowRight size={17} />
                </B>
              </div>
            </form>
          )}
          {step === 2 && (
            <div>
              <h2>One last look.</h2>
              <p className="muted">Good choices deserve a moment.</p>
              <div className="review-block">
                <div className="between">
                  <h3>Your details</h3>
                  <B className="text-link" onClick={() => setStep(0)}>
                    Edit
                  </B>
                </div>
                <p>
                  {address.firstName} {address.lastName}
                  <br />
                  {address.email}
                  <br />
                  {address.phone}
                </p>
              </div>
              <div className="review-block">
                <div className="between">
                  <h3>
                    {method === "delivery" ? "Delivery address" : "Collection"}
                  </h3>
                  <B className="text-link" onClick={() => setStep(1)}>
                    Edit
                  </B>
                </div>
                <p>
                  {method === "delivery" ? (
                    <>
                      {address.street}
                      <br />
                      {address.city}, {address.postal}
                      <br />
                      {address.province}, South Africa
                    </>
                  ) : (
                    "Complimentary collection in Gauteng, by arrangement."
                  )}
                </p>
              </div>
              <div className="payment-note">
                <ShieldCheck size={24} />
                <div>
                  <strong>Pay securely with Peach</strong>
                  <p>
                    You’ll continue to a secure hosted payment page. Your
                    payment details stay with the payment provider.
                  </p>
                </div>
              </div>
              <label className="checkbox-label terms">
                <input
                  type="checkbox"
                  checked={terms}
                  onChange={(e) => setTerms(e.target.checked)}
                />{" "}
                I’ve reviewed my order and delivery details.
              </label>
              <B
                className="btn dark full"
                disabled={!terms}
                onClick={() => setPayment(true)}
              >
                Continue to secure payment · {money(total + shipping)}{" "}
                <ArrowRight size={17} />
              </B>
              <p className="demo-note">
                Design preview — all payments are simulated.
              </p>
            </div>
          )}
        </div>
        <aside className="order-summary">
          <span className="eyebrow">YOUR CONSIDERED PIECES</span>
          <h2>Order summary</h2>
          {cart.map((line) => {
            const p = products.find((x) => x.id === line.productId)!;
            return (
              <div className="summary-item" key={line.key}>
                <img src={img(p.image)} alt={p.type} />
                <div>
                  <h3>{p.name}</h3>
                  <p>{p.type}</p>
                  <small>
                    {p.finishes[line.finish].name} · Qty {line.quantity}
                  </small>
                </div>
                <span>{money(line.quantity * line.price)}</span>
              </div>
            );
          })}
          <div className="summary-totals">
            <div>
              <span>Subtotal</span>
              <span>{money(total)}</span>
            </div>
            <div>
              <span>{method === "delivery" ? "Delivery" : "Collection"}</span>
              <span>{shipping ? money(shipping) : "Complimentary"}</span>
            </div>
            <div className="grand-total">
              <strong>Total</strong>
              <strong>{money(total + shipping)}</strong>
            </div>
            <small>
              Including {money(((total + shipping) * 15) / 115)} VAT
            </small>
          </div>
          <div className="secure-note">
            <ShieldCheck size={15} /> Thoughtful service. Secure payment.
          </div>
        </aside>
      </div>
      <Dialog open={payment} onOpenChange={setPayment}>
        <DialogContent
          className="panel center-panel payment-preview"
          showCloseButton={false}
        >
          <div className="panel-header">
            <DialogTitle>Secure payment preview</DialogTitle>
            <B
              className="icon-btn"
              aria-label="Close payment"
              onClick={() => setPayment(false)}
            >
              <X />
            </B>
          </div>
          <DialogDescription className="sr-only">
            Simulated hosted payment. No money is taken.
          </DialogDescription>
          <div className="auth-content">
            <span className="peach-logo">
              peach<span> payments</span>
            </span>
            <ShieldCheck size={38} />
            <h3>{money(total + shipping)}</h3>
            <p>
              In the live store, this step opens Peach’s secure payment page.
              Use the button below to preview a successful payment.
            </p>
            <B className="btn dark full" onClick={complete}>
              Simulate successful payment <Check size={17} />
            </B>
            <B className="text-link center" onClick={() => setPayment(false)}>
              Return to checkout
            </B>
            <small className="demo-note">
              No real transaction. No card information collected.
            </small>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export function Account({
  identity,
  orders,
  address,
  setAddress,
  onShop,
  onLogout,
}: {
  identity: string;
  orders: Order[];
  address: Address | null;
  setAddress: (value: Address) => void;
  onShop: () => void;
  onLogout: () => void;
}) {
  const [tab, setTab] = useState("Orders"),
    [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(sampleAddress),
    [openOrder, setOpenOrder] = useState<string | null>(null);
  return (
    <section className="account-page wrap">
      <span className="eyebrow">YOUR VELLANO</span>
      <div className="account-heading">
        <div>
          <h1>Welcome home.</h1>
          <p>{identity}</p>
        </div>
        <B className="text-link" onClick={onLogout}>
          Sign out <ArrowRight size={15} />
        </B>
      </div>
      <div className="account-layout">
        <nav className="account-tabs" aria-label="Account">
          <B
            className={tab === "Orders" ? "selected" : ""}
            onClick={() => setTab("Orders")}
          >
            <Package size={18} /> Your orders <span>{orders.length}</span>
          </B>
          <B
            className={tab === "Addresses" ? "selected" : ""}
            onClick={() => setTab("Addresses")}
          >
            <MapPin size={18} /> Saved addresses
          </B>
          <div className="account-aside-note">
            <ShieldCheck size={24} />
            <p>
              One less password to remember.
              <br />
              Your account uses a secure email link.
            </p>
          </div>
        </nav>
        <div className="account-content">
          <h2>
            {tab === "Orders"
              ? "Your considered pieces."
              : "A place to call home."}
          </h2>
          {tab === "Orders" ? (
            orders.length ? (
              <div className="orders-list">
                {orders.map((o) => (
                  <div className="order-history" key={o.id}>
                    <B
                      className="order-history-toggle"
                      aria-expanded={openOrder === o.id}
                      onClick={() =>
                        setOpenOrder(openOrder === o.id ? null : o.id)
                      }
                    >
                      <span>
                        <strong>{o.id}</strong>
                        <small>
                          {o.date} ·{" "}
                          {o.items.reduce((n, x) => n + x.quantity, 0)}{" "}
                          {o.items.reduce((n, x) => n + x.quantity, 0) === 1
                            ? "piece"
                            : "pieces"}
                        </small>
                      </span>
                      <span className="order-status">Confirmed</span>
                      <span>{money(o.total)}</span>
                      <ChevronDown size={17} />
                    </B>
                    {openOrder === o.id && (
                      <div className="order-history-details">
                        {o.items.map((x) => {
                          const p = products.find((p) => p.id === x.productId)!;
                          return (
                            <div key={x.key} className="summary-item">
                              <img src={img(p.image)} alt={p.type} />
                              <div>
                                <h3>{p.name}</h3>
                                <small>
                                  {p.finishes[x.finish].name} · Qty {x.quantity}
                                </small>
                              </div>
                              <span>{money(x.price * x.quantity)}</span>
                            </div>
                          );
                        })}
                        <p>
                          {o.delivery === "delivery"
                            ? "We’ll be in touch to arrange delivery."
                            : "We’ll contact you to arrange collection."}
                        </p>
                        <small className="demo-note">
                          Simulated order. Contact the team for changes or
                          returns in the live store.
                        </small>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <Package size={36} />
                <h3>Your story starts here.</h3>
                <p>
                  Your orders will appear here once you’ve found your first
                  piece.
                </p>
                <B className="btn dark" onClick={onShop}>
                  Explore the collection <ArrowRight size={17} />
                </B>
              </div>
            )
          ) : (
            <>
              {address ? (
                <div className="address-card">
                  <span className="eyebrow">HOME · DEFAULT ADDRESS</span>
                  <h3>
                    {address.firstName} {address.lastName}
                  </h3>
                  <p>
                    {address.street}
                    <br />
                    {address.city}, {address.postal}
                    <br />
                    {address.province}, South Africa
                  </p>
                  <B
                    className="text-link"
                    onClick={() => {
                      setDraft(address);
                      setEditing(true);
                    }}
                  >
                    Edit address <ArrowRight size={15} />
                  </B>
                </div>
              ) : (
                <B className="add-address" onClick={() => setEditing(true)}>
                  <Plus size={27} />
                  <span>Add your first address</span>
                  <small>Make your next checkout a little easier.</small>
                </B>
              )}
            </>
          )}
        </div>
      </div>
      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent className="panel center-panel" showCloseButton={false}>
          <div className="panel-header">
            <DialogTitle>Your home address</DialogTitle>
            <B
              className="icon-btn"
              aria-label="Close address form"
              onClick={() => setEditing(false)}
            >
              <X />
            </B>
          </div>
          <DialogDescription className="sr-only">
            Save an illustrative address in this prototype.
          </DialogDescription>
          <form
            className="address-form"
            onSubmit={(e) => {
              e.preventDefault();
              setAddress(draft);
              setEditing(false);
            }}
          >
            <div className="field-grid">
              {(
                ["firstName", "lastName", "street", "city", "postal"] as const
              ).map((key) => (
                <TextInput
                  key={key}
                  className={key === "street" ? "span-2" : ""}
                  required
                  label={
                    {
                      firstName: "First name",
                      lastName: "Last name",
                      street: "Street address",
                      city: "City",
                      postal: "Postal code",
                    }[key]
                  }
                  value={draft[key]}
                  onChange={(e) =>
                    setDraft({ ...draft, [key]: e.target.value })
                  }
                />
              ))}
            </div>
            <B className="btn dark full" type="submit">
              Save address <Check size={17} />
            </B>
            <small className="demo-note">
              Saved for this preview session only.
            </small>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  );
}
