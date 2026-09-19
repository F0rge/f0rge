/** Shared interaction wiring — variants only differ in markup. */
window.VellanoProto = window.VellanoProto || {};

VellanoProto.wireCommerce = function (root, state, go, render) {
  VellanoProto.bindNav(root, state, go);

  root.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-add");
      const form = btn.closest("[data-pdp]") || root;
      const fabric =
        (form.querySelector("[name=fabric]:checked") || {}).value ||
        (form.querySelector("[data-fabric-val]") || {}).value;
      const size =
        (form.querySelector("[name=size]:checked") || {}).value ||
        (form.querySelector("[data-size-val]") || {}).value;
      const p = VellanoProto.PRODUCTS.find((x) => x.id === id);
      VellanoProto.addToCart(
        state,
        id,
        fabric || p.defaultFabric,
        size || p.defaultSize
      );
      render();
    });
  });

  root.querySelectorAll("[data-qty]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = +btn.getAttribute("data-idx");
      const delta = +btn.getAttribute("data-qty");
      VellanoProto.setQty(state, idx, state.cart[idx].qty + delta);
      render();
    });
  });

  root.querySelectorAll("[data-sku-sync]").forEach((el) => {
    el.addEventListener("change", () => {
      const fabric = (root.querySelector("[name=fabric]:checked") || {}).value;
      const size = (root.querySelector("[name=size]:checked") || {}).value;
      if (fabric) state.pdpFabric = fabric;
      if (size) state.pdpSize = size;
      render();
    });
  });

  const checkoutForm = root.querySelector("[data-checkout-form]");
  if (checkoutForm) {
    checkoutForm.addEventListener("input", (e) => {
      const t = e.target;
      if (!t.name) return;
      if (t.name === "shippingId") state.checkout.shippingId = t.value;
      else if (t.name === "saveAddress") state.checkout.saveAddress = t.checked;
      else if (t.name in state.checkout) state.checkout[t.name] = t.value;
    });
    checkoutForm.addEventListener("change", (e) => {
      if (e.target.name === "shippingId") render();
    });
  }

  root.querySelectorAll("[data-start-hold]").forEach((btn) => {
    btn.addEventListener("click", () => {
      VellanoProto.startSoftHold(state);
      render();
    });
  });

  root.querySelectorAll("[data-peach]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!state.checkout.email || !state.checkout.name) {
        state.toast = "Email + name required for guest checkout";
        render();
        return;
      }
      if (!state.checkout.holdStartedAt) VellanoProto.startSoftHold(state);
      await VellanoProto.mockPeachPay(state);
      state.view = "orders";
      render();
    });
  });

  root.querySelectorAll("[data-magic-send]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const email =
        (root.querySelector("[name=magicEmail]") || {}).value ||
        (state.user && state.user.email) ||
        state.checkout.email;
      if (!email) {
        state.toast = "Enter an email for magic link";
        render();
        return;
      }
      VellanoProto.sendMagicLink(state, email);
      render();
    });
  });

  root.querySelectorAll("[data-magic-confirm]").forEach((btn) => {
    btn.addEventListener("click", () => {
      VellanoProto.confirmMagic(state);
      render();
    });
  });

  root.querySelectorAll("[data-signout]").forEach((btn) => {
    btn.addEventListener("click", () => {
      VellanoProto.signOut(state);
      render();
    });
  });

  root.querySelectorAll("[data-use-address]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-use-address");
      const a = state.addresses.find((x) => x.id === id);
      if (!a) return;
      state.checkout.name = a.name;
      state.checkout.addressLine = a.line;
      state.checkout.city = a.city;
      state.checkout.province = a.province;
      state.checkout.postal = a.postal;
      state.checkout.phone = a.phone;
      state.view = "checkout";
      state.toast = "Address applied to checkout";
      render();
    });
  });
};

VellanoProto.selectedSku = function (root, product) {
  const fabric =
    (root.querySelector("[name=fabric]:checked") || {}).value ||
    product.defaultFabric;
  const size =
    (root.querySelector("[name=size]:checked") || {}).value ||
    product.defaultSize;
  return { fabric, size, price: VellanoProto.skuPrice(product, size) };
};

VellanoProto.variantRadios = function (product, name, options, selected) {
  return options
    .map(
      (o) =>
        '<label class="opt"><input type="radio" name="' +
        name +
        '" value="' +
        o +
        '" data-sku-sync ' +
        (o === selected ? "checked" : "") +
        " /><span>" +
        o +
        "</span></label>"
    )
    .join("");
};

VellanoProto.cartLinesHtml = function (state, dense) {
  if (!state.cart.length) {
    return '<p class="empty">Your cart is empty.</p>';
  }
  return state.cart
    .map((line, idx) => {
      const p = VellanoProto.PRODUCTS.find((x) => x.id === line.productId);
      const price = VellanoProto.skuPrice(p, line.size) * line.qty;
      return (
        '<div class="cart-line' +
        (dense ? " dense" : "") +
        '">' +
        VellanoProto.swatch(p.hue, p.name) +
        '<div class="cart-meta"><strong>' +
        p.name +
        "</strong><span>" +
        line.fabric +
        " · " +
        line.size +
        '</span></div><div class="qty"><button type="button" data-qty="-1" data-idx="' +
        idx +
        '">−</button><span>' +
        line.qty +
        '</span><button type="button" data-qty="1" data-idx="' +
        idx +
        '">+</button></div><div class="line-price">' +
        VellanoProto.fmt(price) +
        "</div></div>"
      );
    })
    .join("");
};

VellanoProto.shippingOptionsHtml = function (state) {
  return VellanoProto.SHIPPING.map((s) => {
    const checked = state.checkout.shippingId === s.id ? "checked" : "";
    return (
      '<label class="ship-opt"><input type="radio" name="shippingId" value="' +
      s.id +
      '" ' +
      checked +
      " /><div><strong>" +
      s.label +
      "</strong><span>" +
      s.detail +
      " · " +
      s.eta +
      "</span></div><em>" +
      (s.price ? VellanoProto.fmt(s.price) : "Free") +
      "</em></label>"
    );
  }).join("");
};

VellanoProto.checkoutTotals = function (state) {
  const sub = VellanoProto.cartSubtotal(state);
  const ship =
    VellanoProto.SHIPPING.find((s) => s.id === state.checkout.shippingId) ||
    VellanoProto.SHIPPING[0];
  return { sub, ship, total: sub + ship.price };
};
