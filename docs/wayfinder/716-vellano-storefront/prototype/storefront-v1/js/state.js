/** In-memory prototype state — no persistence (#720). */
window.VellanoProto = window.VellanoProto || {};

VellanoProto.createState = function () {
  return {
    view: "home", // home | product | cart | checkout | account | orders | addresses
    productId: null,
    search: "",
    collection: "All",
    pdpFabric: null,
    pdpSize: null,
    cart: [], // { productId, fabric, size, qty }
    checkout: {
      email: "",
      name: "",
      phone: "",
      shippingId: "gauteng",
      addressLine: "",
      city: "",
      province: "Gauteng",
      postal: "",
      saveAddress: true,
      holdStartedAt: null,
      holdMinutes: 20,
      peachStatus: "idle", // idle | processing | success | fail
      orderId: null,
    },
    user: null, // { email, magicSent, signedIn }
    orders: [],
    addresses: [],
    toast: null,
  };
};

VellanoProto.cartCount = function (state) {
  return state.cart.reduce((n, l) => n + l.qty, 0);
};

VellanoProto.cartSubtotal = function (state) {
  return state.cart.reduce((sum, line) => {
    const p = VellanoProto.PRODUCTS.find((x) => x.id === line.productId);
    if (!p) return sum;
    return sum + VellanoProto.skuPrice(p, line.size) * line.qty;
  }, 0);
};

VellanoProto.addToCart = function (state, productId, fabric, size) {
  const existing = state.cart.find(
    (l) => l.productId === productId && l.fabric === fabric && l.size === size
  );
  if (existing) existing.qty += 1;
  else state.cart.push({ productId, fabric, size, qty: 1 });
  state.toast = "Added to cart (no stock hold yet)";
};

VellanoProto.setQty = function (state, idx, qty) {
  if (qty <= 0) state.cart.splice(idx, 1);
  else state.cart[idx].qty = qty;
};

VellanoProto.startSoftHold = function (state) {
  state.checkout.holdStartedAt = Date.now();
  state.toast = "Soft hold started (mock 20 min TTL)";
};

VellanoProto.mockPeachPay = function (state) {
  state.checkout.peachStatus = "processing";
  return new Promise((resolve) => {
    setTimeout(() => {
      state.checkout.peachStatus = "success";
      const id = "ORD-" + String(1000 + state.orders.length + 1);
      state.checkout.orderId = id;
      const ship = VellanoProto.SHIPPING.find(
        (s) => s.id === state.checkout.shippingId
      );
      const order = {
        id,
        placedAt: new Date().toISOString(),
        email: state.checkout.email,
        lines: state.cart.map((l) => ({ ...l })),
        shipping: ship,
        total:
          VellanoProto.cartSubtotal(state) + (ship ? ship.price : 0),
        status: "Paid · stock committed (mock)",
      };
      state.orders.unshift(order);
      if (state.checkout.saveAddress && state.checkout.addressLine) {
        const addr = {
          id: "addr-" + (state.addresses.length + 1),
          label: "Home",
          name: state.checkout.name,
          line: state.checkout.addressLine,
          city: state.checkout.city,
          province: state.checkout.province,
          postal: state.checkout.postal,
          phone: state.checkout.phone,
        };
        const dup = state.addresses.find(
          (a) => a.line === addr.line && a.postal === addr.postal
        );
        if (!dup) state.addresses.push(addr);
      }
      if (state.user && state.user.signedIn) {
        /* already linked */
      } else if (state.checkout.email) {
        state.user = {
          email: state.checkout.email,
          magicSent: false,
          signedIn: false,
        };
      }
      state.cart = [];
      state.checkout.holdStartedAt = null;
      state.toast = "Peach mock success · order " + id;
      resolve(order);
    }, 900);
  });
};

VellanoProto.sendMagicLink = function (state, email) {
  state.user = { email, magicSent: true, signedIn: false };
  state.toast = "Magic link sent (mock) — click Confirm below";
};

VellanoProto.confirmMagic = function (state) {
  if (!state.user) return;
  state.user.signedIn = true;
  state.user.magicSent = false;
  state.toast = "Signed in via passwordless (mock Clerk)";
};

VellanoProto.signOut = function (state) {
  state.user = null;
  state.toast = "Signed out";
};

VellanoProto.stateSnapshot = function (state) {
  return {
    view: state.view,
    productId: state.productId,
    search: state.search,
    collection: state.collection,
    cart: state.cart,
    cartCount: VellanoProto.cartCount(state),
    cartSubtotal: VellanoProto.cartSubtotal(state),
    checkout: {
      email: state.checkout.email,
      shippingId: state.checkout.shippingId,
      holdStartedAt: state.checkout.holdStartedAt,
      peachStatus: state.checkout.peachStatus,
      orderId: state.checkout.orderId,
    },
    user: state.user,
    ordersCount: state.orders.length,
    addressesCount: state.addresses.length,
  };
};
