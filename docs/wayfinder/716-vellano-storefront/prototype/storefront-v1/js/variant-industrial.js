/** Variant C — Bold industrial (dark, dense, price-first, sticky buy). */
window.VellanoProto = window.VellanoProto || {};
VellanoProto.VARIANTS = VellanoProto.VARIANTS || {};

VellanoProto.VARIANTS.industrial = {
  key: "industrial",
  label: "Bold industrial",
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
      '<div class="v-industrial">' +
      '<header class="in-bar">' +
      '<div class="in-brand"><a href="#" data-go="home">' +
      B.name.toUpperCase() +
      '</a><span>STOREFRONT // V1</span></div>' +
      '<input data-search placeholder="FILTER SKUs…" value="' +
      (state.search || "").replace(/"/g, "&quot;") +
      '" />' +
      '<nav>' +
      '<a href="#" data-go="home">CATALOGUE</a>' +
      '<a href="#" data-go="account">ID</a>' +
      '<a href="#" data-go="orders">ORDERS</a>' +
      '<a href="#" data-go="addresses">ADDR</a>' +
      '<a href="#" data-go="cart" class="in-cart">CART ' +
      count +
      "</a></nav></header>" +
      body +
      (state.cart.length && state.view !== "cart" && state.view !== "checkout"
        ? '<div class="in-dock"><span>' +
          count +
          " in cart · " +
          VellanoProto.fmt(VellanoProto.cartSubtotal(state)) +
          '</span><button type="button" data-go="cart">OPEN CART</button></div>'
        : "") +
      "</div>"
    );
  },

  home(state) {
    const products = VellanoProto.filteredProducts(state);
    const tabs = VellanoProto.collections()
      .map(
        (c) =>
          '<button type="button" class="' +
          (state.collection === c ? "on" : "") +
          '" data-collection="' +
          c +
          '">' +
          c.toUpperCase() +
          "</button>"
      )
      .join("");
    const rows = products
      .map(
        (p) =>
          '<button type="button" class="in-row" data-go="product" data-product="' +
          p.id +
          '">' +
          '<span class="in-sw" style="background:' +
          p.hue +
          '"></span>' +
          '<span class="in-name">' +
          p.name +
          '</span><span class="in-col">' +
          p.collection +
          '</span><span class="in-price">' +
          VellanoProto.fmt(p.priceFrom) +
          "</span></button>"
      )
      .join("");
    return (
      '<section class="in-home"><div class="in-hero-block"><h1>STOCK ON THE FLOOR.</h1>' +
      "<p>Showroom + domestic. Soft hold at pay. Peach mock.</p></div>" +
      '<div class="in-tabs">' +
      tabs +
      '</div><div class="in-table">' +
      '<div class="in-head"><span></span><span>SKU</span><span>LINE</span><span>FROM</span></div>' +
      (rows || '<p class="empty">NO MATCH</p>') +
      "</div></section>"
    );
  },

  pdp(state) {
    const p = VellanoProto.PRODUCTS.find((x) => x.id === state.productId);
    if (!p) return '<p class="empty">MISSING</p>';
    return (
      '<section class="in-pdp" data-pdp>' +
      '<div class="in-pdp-left" style="--hue:' +
      p.hue +
      '"><div class="in-plate">' +
      p.id.toUpperCase() +
      "</div></div>" +
      '<div class="in-pdp-right">' +
      "<h1>" +
      p.name.toUpperCase() +
      "</h1><p>" +
      p.blurb +
      '</p>' +
      '<table class="in-specs"><tr><th>COLLECTION</th><td>' +
      p.collection +
      "</td></tr><tr><th>VAT</th><td>INCLUDED</td></tr></table>" +
      "<h4>FINISH</h4><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "fabric", p.fabrics, state.pdpFabric || p.defaultFabric) +
      "</div><h4>SIZE</h4><div class=\"opts\">" +
      VellanoProto.variantRadios(p, "size", p.sizes, state.pdpSize || p.defaultSize) +
      '</div>' +
      '<div class="in-buy">' +
      '<strong data-live-price>' +
      VellanoProto.fmt(VellanoProto.skuPrice(p, state.pdpSize || p.defaultSize)) +
      '</strong>' +
      '<button type="button" data-add="' +
      p.id +
      '">ADD TO CART</button></div></div></section>'
    );
  },

  cart(state) {
    const sub = VellanoProto.cartSubtotal(state);
    return (
      '<section class="in-cart-page"><h1>CART</h1>' +
      VellanoProto.cartLinesHtml(state, true) +
      '<div class="in-buy"><strong>' +
      VellanoProto.fmt(sub) +
      '</strong>' +
      (state.cart.length
        ? '<button type="button" data-go="checkout">CHECKOUT AS GUEST</button>'
        : "") +
      "</div></section>"
    );
  },

  checkout(state) {
    const t = VellanoProto.checkoutTotals(state);
    const hold = VellanoProto.holdRemaining(state);
    const c = state.checkout;
    return (
      '<section class="in-checkout"><h1>CHECKOUT // GUEST</h1>' +
      (hold
        ? '<div class="hold-banner">HOLD TTL ' + hold + "</div>"
        : '<button type="button" data-start-hold>ARM SOFT HOLD</button>') +
      '<form data-checkout-form class="in-form">' +
      '<div class="row2"><label>EMAIL<input name="email" type="email" value="' +
      (c.email || "") +
      '" /></label><label>NAME<input name="name" value="' +
      (c.name || "") +
      '" /></label></div>' +
      '<label>PHONE<input name="phone" value="' +
      (c.phone || "") +
      '" /></label>' +
      "<h3>FULFILLMENT</h3>" +
      VellanoProto.shippingOptionsHtml(state) +
      (c.shippingId !== "showroom"
        ? '<label>STREET<input name="addressLine" value="' +
          (c.addressLine || "") +
          '" /></label>' +
          '<div class="row2"><label>CITY<input name="city" value="' +
          (c.city || "") +
          '" /></label><label>POSTAL<input name="postal" value="' +
          (c.postal || "") +
          '" /></label></div>' +
          '<label>PROVINCE<input name="province" value="' +
          (c.province || "") +
          '" /></label>'
        : "") +
      '<label class="check"><input type="checkbox" name="saveAddress" ' +
      (c.saveAddress ? "checked" : "") +
      " /> SAVE ADDR</label>" +
      '<div class="in-buy"><strong>' +
      VellanoProto.fmt(t.total) +
      '</strong><button type="button" data-peach>PEACH PAY</button></div></form></section>'
    );
  },

  account(state) {
    const u = state.user;
    return (
      '<section class="in-account"><h1>IDENTITY</h1>' +
      (u && u.signedIn
        ? "<p>" +
          u.email +
          ' · LIVE</p><button type="button" data-signout>SIGN OUT</button>'
        : '<p>OPTIONAL MAGIC LINK (CLERK MOCK)</p><input name="magicEmail" type="email" placeholder="you@email" value="' +
          ((u && u.email) || "") +
          '" />' +
          '<button type="button" data-magic-send>SEND LINK</button>' +
          (u && u.magicSent
            ? '<button type="button" data-magic-confirm>CONFIRM LINK</button>'
            : "")) +
      "</section>"
    );
  },

  orders(state) {
    if (!state.orders.length) return '<section class="in-pad"><h1>ORDERS</h1><p class="empty">NONE</p></section>';
    return (
      '<section class="in-orders"><h1>ORDERS</h1>' +
      state.orders
        .map(
          (o) =>
            '<div class="in-order"><code>' +
            o.id +
            "</code> " +
            VellanoProto.fmt(o.total) +
            " · " +
            o.status +
            "</div>"
        )
        .join("") +
      "</section>"
    );
  },

  addresses(state) {
    if (!state.addresses.length)
      return '<section class="in-pad"><h1>ADDRESSES</h1><p class="empty">NONE</p></section>';
    return (
      '<section class="in-addrs"><h1>ADDRESSES</h1>' +
      state.addresses
        .map(
          (a) =>
            '<div class="in-addr">' +
            a.line +
            " / " +
            a.city +
            ' <button type="button" data-use-address="' +
            a.id +
            '">USE</button></div>'
        )
        .join("") +
      "</section>"
    );
  },
};
