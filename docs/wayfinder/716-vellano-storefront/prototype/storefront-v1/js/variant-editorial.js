/** Variant A — Editorial gallery (magazine / horizontal strips). */
window.VellanoProto = window.VellanoProto || {};
VellanoProto.VARIANTS = VellanoProto.VARIANTS || {};

VellanoProto.VARIANTS.editorial = {
  key: "editorial",
  label: "Editorial gallery",
  render(state) {
    const B = VellanoProto.BRAND;
    const count = VellanoProto.cartCount(state);
    let body = "";
    if (state.view === "home") body = this.home(state);
    else if (state.view === "product") body = this.pdp(state);
    else if (state.view === "cart") body = this.cart(state);
    else if (state.view === "checkout") body = this.checkout(state);
    else if (state.view === "account") body = this.account(state);
    else if (state.view === "orders") body = this.orders(state);
    else if (state.view === "addresses") body = this.addresses(state);

    return (
      '<div class="v-editorial">' +
      '<header class="ed-nav">' +
      '<a href="#" data-go="home" class="ed-logo">' + B.name + "</a>" +
      '<nav class="ed-links">' +
      '<a href="#" data-go="home">Catalogue</a>' +
      '<a href="#" data-go="account">Account</a>' +
      '<a href="#" data-go="orders">Orders</a>' +
      '<a href="#" data-go="addresses">Addresses</a>' +
      '</nav>' +
      '<button type="button" class="ed-cart" data-go="cart">Bag <em>' + count + "</em></button>" +
      "</header>" +
      body +
      '<footer class="ed-foot"><span>' + B.vatNote + "</span><span>Showroom · Johannesburg</span></footer>" +
      "</div>"
    );
  },

  home(state) {
    const products = VellanoProto.filteredProducts(state);
    const cols = VellanoProto.collections();
    const strips = cols
      .filter((c) => c !== "All")
      .map((col) => {
        const items = products.filter((p) => p.collection === col);
        if (!items.length && state.collection !== "All" && state.collection !== col) return "";
        const cards = (state.collection === "All" || state.collection === col ? items : [])
          .map(
            (p) =>
              '<article class="ed-card" data-go="product" data-product="' +
              p.id +
              '">' +
              VellanoProto.swatch(p.hue, p.name) +
              "<h3>" +
              p.name +
              "</h3><p>from " +
              VellanoProto.fmt(p.priceFrom) +
              "</p></article>"
          )
          .join("");
        if (!cards && state.search) return "";
        return (
          '<section class="ed-strip"><div class="ed-strip-head"><h2>' +
          col +
          '</h2><button type="button" data-collection="' +
          col +
          '">Focus</button></div><div class="ed-rail">' +
          cards +
          "</div></section>"
        );
      })
      .join("");

    return (
      '<section class="ed-hero"><p class="eyebrow">V1 prototype · curated SKUs</p>' +
      "<h1>Furniture with room<br/>to breathe.</h1>" +
      "<p class=\"lede\">" +
      VellanoProto.BRAND.tagline +
      " · ZAR VAT-inc</p>" +
      '<div class="ed-search"><input data-search placeholder="Search sofas, oak, lighting…" value="' +
      (state.search || "").replace(/"/g, "&quot;") +
      '" />' +
      '<div class="ed-pills">' +
      cols
        .map(
          (c) =>
            '<button type="button" class="' +
            (state.collection === c ? "on" : "") +
            '" data-collection="' +
            c +
            '">' +
            c +
            "</button>"
        )
        .join("") +
      "</div></div></section>" +
      (strips || '<p class="empty ed-pad">No pieces match.</p>')
    );
  },

  pdp(state) {
    const p = VellanoProto.PRODUCTS.find((x) => x.id === state.productId);
    if (!p) return '<p class="empty">Product missing.</p>';
    const fabric = state.pdpFabric || p.defaultFabric;
    const size = state.pdpSize || p.defaultSize;
    // Will re-read from radios after mount; initial price from defaults
    const price = VellanoProto.skuPrice(p, size);
    return (
      '<article class="ed-pdp" data-pdp>' +
      '<div class="ed-pdp-visual" style="--hue:' +
      p.hue +
      '"><span>' +
      p.collection +
      "</span><strong>" +
      p.name.split(" ")[0] +
      "</strong></div>" +
      '<div class="ed-pdp-copy">' +
      '<p class="eyebrow">' +
      p.collection +
      "</p><h1>" +
      p.name +
      "</h1><p class=\"lede\">" +
      p.blurb +
      '</p><p class="ed-price" data-live-price>' +
      VellanoProto.fmt(price) +
      ' <small>VAT incl.</small></p>' +
      "<h4>Fabric / finish</h4><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "fabric", p.fabrics, fabric) +
      "</div><h4>Size</h4><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "size", p.sizes, size) +
      '</div><button type="button" class="ed-cta" data-add="' +
      p.id +
      '">Add to bag</button>' +
      '<p class="hint">Stock soft-hold only begins at checkout.</p></div></article>'
    );
  },

  cart(state) {
    const sub = VellanoProto.cartSubtotal(state);
    return (
      '<section class="ed-cart-page"><h1>Bag</h1>' +
      VellanoProto.cartLinesHtml(state) +
      '<div class="ed-cart-foot"><span>Subtotal · ' +
      VellanoProto.BRAND.vatNote +
      "</span><strong>" +
      VellanoProto.fmt(sub) +
      '</strong>' +
      (state.cart.length
        ? '<button type="button" class="ed-cta" data-go="checkout">Guest checkout</button>'
        : "") +
      "</div></section>"
    );
  },

  checkout(state) {
    const t = VellanoProto.checkoutTotals(state);
    const hold = VellanoProto.holdRemaining(state);
    const c = state.checkout;
    return (
      '<section class="ed-checkout"><h1>Checkout</h1>' +
      '<p class="lede">Guest-first · optional magic-link account after pay</p>' +
      (hold
        ? '<div class="hold-banner">Soft hold active · <strong>' + hold + "</strong> remaining</div>"
        : '<button type="button" data-start-hold class="ghost">Start soft hold (mock)</button>') +
      '<form data-checkout-form class="ed-form">' +
      '<label>Email<input name="email" type="email" value="' +
      (c.email || "") +
      '" required /></label>' +
      '<label>Full name<input name="name" value="' +
      (c.name || "") +
      '" required /></label>' +
      '<label>Phone<input name="phone" value="' +
      (c.phone || "") +
      '" /></label>' +
      "<h3>Ship or collect</h3>" +
      VellanoProto.shippingOptionsHtml(state) +
      (c.shippingId !== "showroom"
        ? '<label>Street<input name="addressLine" value="' +
          (c.addressLine || "") +
          '" /></label>' +
          '<div class="row2"><label>City<input name="city" value="' +
          (c.city || "") +
          '" /></label><label>Postal<input name="postal" value="' +
          (c.postal || "") +
          '" /></label></div>' +
          '<label>Province<input name="province" value="' +
          (c.province || "") +
          '" /></label>'
        : "") +
      '<label class="check"><input type="checkbox" name="saveAddress" ' +
      (c.saveAddress ? "checked" : "") +
      " /> Save address if I create an account</label>" +
      "</form>" +
      '<aside class="ed-summary"><h3>Order</h3>' +
      VellanoProto.cartLinesHtml(state, true) +
      "<dl><dt>Subtotal</dt><dd>" +
      VellanoProto.fmt(t.sub) +
      "</dd><dt>Shipping</dt><dd>" +
      (t.ship.price ? VellanoProto.fmt(t.ship.price) : "Free") +
      "</dd><dt>Total</dt><dd>" +
      VellanoProto.fmt(t.total) +
      '</dd></dl>' +
      '<button type="button" class="ed-cta" data-peach>Pay with Peach (mock)</button>' +
      '<p class="hint">Peach Payments · mock only · ZAR</p></aside></section>'
    );
  },

  account(state) {
    const u = state.user;
    return (
      '<section class="ed-account"><h1>Account</h1>' +
      '<p class="lede">Optional passwordless (Clerk-style magic link)</p>' +
      (u && u.signedIn
        ? '<p class="ok">Signed in as <strong>' +
          u.email +
          '</strong></p><button type="button" data-signout class="ghost">Sign out</button>' +
          '<div class="ed-account-links"><a href="#" data-go="orders">Order history</a><a href="#" data-go="addresses">Saved addresses</a></div>'
        : '<div class="ed-form"><label>Email<input name="magicEmail" type="email" value="' +
          ((u && u.email) || "") +
          '" /></label>' +
          '<button type="button" class="ed-cta" data-magic-send>Email me a magic link</button>' +
          (u && u.magicSent
            ? '<button type="button" class="ghost" data-magic-confirm>Confirm magic link (mock)</button>'
            : "") +
          "</div>") +
      "</section>"
    );
  },

  orders(state) {
    if (!state.orders.length)
      return '<section class="ed-pad"><h1>Orders</h1><p class="empty">No orders yet — complete a mock Peach pay.</p></section>';
    return (
      '<section class="ed-orders"><h1>Orders</h1>' +
      state.orders
        .map((o) => {
          const lines = o.lines
            .map((l) => {
              const p = VellanoProto.PRODUCTS.find((x) => x.id === l.productId);
              return "<li>" + p.name + " · " + l.fabric + " · " + l.size + " ×" + l.qty + "</li>";
            })
            .join("");
          return (
            '<article class="ed-order"><header><strong>' +
            o.id +
            "</strong><span>" +
            new Date(o.placedAt).toLocaleString("en-ZA") +
            "</span></header><ul>" +
            lines +
            "</ul><p>" +
            o.status +
            " · " +
            VellanoProto.fmt(o.total) +
            "</p></article>"
          );
        })
        .join("") +
      "</section>"
    );
  },

  addresses(state) {
    if (!state.addresses.length)
      return '<section class="ed-pad"><h1>Saved addresses</h1><p class="empty">None yet — tick “save address” at checkout.</p></section>';
    return (
      '<section class="ed-addrs"><h1>Saved addresses</h1>' +
      state.addresses
        .map(
          (a) =>
            '<article class="ed-addr"><strong>' +
            a.label +
            "</strong><p>" +
            a.name +
            "<br/>" +
            a.line +
            "<br/>" +
            a.city +
            ", " +
            a.province +
            " " +
            a.postal +
            '</p><button type="button" data-use-address="' +
            a.id +
            '">Use at checkout</button></article>'
        )
        .join("") +
      "</section>"
    );
  },
};
