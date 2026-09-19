/** Variant B — Minimal Scandinavian (sidebar filters + airy grid + stepper checkout). */
window.VellanoProto = window.VellanoProto || {};
VellanoProto.VARIANTS = VellanoProto.VARIANTS || {};

VellanoProto.VARIANTS.scandi = {
  key: "scandi",
  label: "Minimal Scandinavian",
  render(state) {
    const B = VellanoProto.BRAND;
    const count = VellanoProto.cartCount(state);
    const u = state.user;
    let body = "";
    if (state.view === "home") body = this.home(state);
    else if (state.view === "product") body = this.pdp(state);
    else if (state.view === "cart") body = this.cart(state);
    else if (state.view === "checkout") body = this.checkout(state);
    else if (state.view === "account") body = this.account(state);
    else if (state.view === "orders") body = this.orders(state);
    else if (state.view === "addresses") body = this.addresses(state);

    return (
      '<div class="v-scandi">' +
      '<header class="sc-top">' +
      '<a href="#" data-go="home" class="sc-logo">' + B.name + "</a>" +
      '<input class="sc-search" data-search placeholder="Search catalogue" value="' +
      (state.search || "").replace(/"/g, "&quot;") +
      '" />' +
      '<div class="sc-actions">' +
      '<a href="#" data-go="account">' +
      (u && u.signedIn ? u.email.split("@")[0] : "Sign in") +
      "</a>" +
      '<a href="#" data-go="cart" class="sc-bag">Cart (' +
      count +
      ")</a></div></header>" +
      '<div class="sc-shell">' +
      '<aside class="sc-side">' +
      "<h4>Browse</h4>" +
      VellanoProto.collections()
        .map(
          (c) =>
            '<button type="button" class="sc-col ' +
            (state.collection === c ? "on" : "") +
            '" data-collection="' +
            c +
            '">' +
            c +
            "</button>"
        )
        .join("") +
      '<hr/><a href="#" data-go="orders">Orders</a>' +
      '<a href="#" data-go="addresses">Addresses</a>' +
      "<p class=\"tiny\">" +
      B.vatNote +
      "</p></aside>" +
      '<main class="sc-main">' +
      body +
      "</main></div></div>"
    );
  },

  home(state) {
    const products = VellanoProto.filteredProducts(state);
    const cards = products
      .map(
        (p) =>
          '<article class="sc-card">' +
          '<button type="button" class="sc-thumb" style="--hue:' +
          p.hue +
          '" data-go="product" data-product="' +
          p.id +
          '"></button>' +
          "<div><span class=\"muted\">" +
          p.collection +
          "</span><h3>" +
          p.name +
          "</h3><p>" +
          p.blurb +
          '</p><div class="sc-card-foot"><strong>' +
          VellanoProto.fmt(p.priceFrom) +
          '+</strong><button type="button" data-go="product" data-product="' +
          p.id +
          '">View</button></div></div></article>'
      )
      .join("");
    return (
      '<div class="sc-home"><header><h1>Catalogue</h1><p class="muted">' +
      products.length +
      " pieces · curated ~30–80 SKU vibe</p></header>" +
      '<div class="sc-grid">' +
      (cards || '<p class="empty">No matches.</p>') +
      "</div></div>"
    );
  },

  pdp(state) {
    const p = VellanoProto.PRODUCTS.find((x) => x.id === state.productId);
    if (!p) return '<p class="empty">Missing product.</p>';
    return (
      '<article class="sc-pdp" data-pdp>' +
      '<div class="sc-pdp-img" style="--hue:' +
      p.hue +
      '"></div>' +
      '<div class="sc-pdp-info">' +
      '<p class="muted">' +
      p.collection +
      "</p><h1>" +
      p.name +
      "</h1><p>" +
      p.blurb +
      '</p><p class="sc-price" data-live-price>' +
      VellanoProto.fmt(VellanoProto.skuPrice(p, state.pdpSize || p.defaultSize)) +
      "</p>" +
      "<fieldset><legend>Finish</legend><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "fabric", p.fabrics, state.pdpFabric || p.defaultFabric) +
      "</div></fieldset>" +
      "<fieldset><legend>Size</legend><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "size", p.sizes, state.pdpSize || p.defaultSize) +
      '</div></fieldset>' +
      '<button type="button" class="sc-btn" data-add="' +
      p.id +
      '">Add to cart</button>' +
      '<p class="tiny">No reservation until checkout soft hold.</p></div></article>'
    );
  },

  cart(state) {
    const sub = VellanoProto.cartSubtotal(state);
    return (
      '<div class="sc-cart"><h1>Cart</h1>' +
      VellanoProto.cartLinesHtml(state) +
      '<div class="sc-total"><span>Subtotal</span><strong>' +
      VellanoProto.fmt(sub) +
      "</strong></div>" +
      (state.cart.length
        ? '<button type="button" class="sc-btn" data-go="checkout">Continue to checkout</button>'
        : "") +
      "</div>"
    );
  },

  checkout(state) {
    const t = VellanoProto.checkoutTotals(state);
    const hold = VellanoProto.holdRemaining(state);
    const c = state.checkout;
    const step = !c.email || !c.name ? 1 : c.shippingId && (c.shippingId === "showroom" || c.addressLine) ? 3 : 2;
    return (
      '<div class="sc-checkout"><h1>Checkout</h1>' +
      '<ol class="sc-steps"><li class="' +
      (step >= 1 ? "on" : "") +
      '">Contact</li><li class="' +
      (step >= 2 ? "on" : "") +
      '">Delivery</li><li class="' +
      (step >= 3 ? "on" : "") +
      '">Pay</li></ol>' +
      (hold
        ? '<div class="hold-banner">Soft hold · ' + hold + "</div>"
        : '<button type="button" class="sc-ghost" data-start-hold>Start soft hold</button>') +
      '<form data-checkout-form class="sc-form">' +
      "<h3>1 · Contact</h3>" +
      '<label>Email<input name="email" type="email" value="' +
      (c.email || "") +
      '" /></label>' +
      '<label>Name<input name="name" value="' +
      (c.name || "") +
      '" /></label>' +
      '<label>Phone<input name="phone" value="' +
      (c.phone || "") +
      '" /></label>' +
      "<h3>2 · Delivery</h3>" +
      VellanoProto.shippingOptionsHtml(state) +
      (c.shippingId !== "showroom"
        ? '<label>Address<input name="addressLine" value="' +
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
        : '<p class="tiny">Collect: Johannesburg Design District showroom.</p>') +
      '<label class="check"><input type="checkbox" name="saveAddress" ' +
      (c.saveAddress ? "checked" : "") +
      " /> Save address to account</label>" +
      "<h3>3 · Payment</h3>" +
      "<p class=\"tiny\">Peach Payments (mock) · total " +
      VellanoProto.fmt(t.total) +
      '</p>' +
      '<button type="button" class="sc-btn" data-peach>Pay ' +
      VellanoProto.fmt(t.total) +
      "</button></form></div>"
    );
  },

  account(state) {
    const u = state.user;
    return (
      '<div class="sc-account"><h1>Account</h1>' +
      (u && u.signedIn
        ? "<p>Hello, <strong>" +
          u.email +
          '</strong></p><button type="button" class="sc-ghost" data-signout>Sign out</button>'
        : '<p class="muted">Passwordless optional — guest checkout works without this.</p>' +
          '<label>Email<input name="magicEmail" type="email" value="' +
          ((u && u.email) || "") +
          '" /></label>' +
          '<button type="button" class="sc-btn" data-magic-send>Send magic link</button>' +
          (u && u.magicSent
            ? '<button type="button" class="sc-ghost" data-magic-confirm>I clicked the link</button>'
            : "")) +
      "</div>"
    );
  },

  orders(state) {
    if (!state.orders.length) return '<div><h1>Orders</h1><p class="empty">Empty.</p></div>';
    return (
      "<div><h1>Order history</h1>" +
      state.orders
        .map(
          (o) =>
            '<div class="sc-order"><strong>' +
            o.id +
            "</strong> · " +
            VellanoProto.fmt(o.total) +
            "<br/><span class=\"muted\">" +
            o.status +
            "</span></div>"
        )
        .join("") +
      "</div>"
    );
  },

  addresses(state) {
    if (!state.addresses.length) return '<div><h1>Addresses</h1><p class="empty">None saved.</p></div>';
    return (
      "<div><h1>Saved addresses</h1>" +
      state.addresses
        .map(
          (a) =>
            '<div class="sc-addr">' +
            a.line +
            ", " +
            a.city +
            ' <button type="button" data-use-address="' +
            a.id +
            '">Use</button></div>'
        )
        .join("") +
      "</div>"
    );
  },
};
