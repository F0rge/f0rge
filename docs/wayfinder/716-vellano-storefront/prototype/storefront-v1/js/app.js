/**
 * Throwaway UI prototype switcher (#720).
 * Plan: Three radically different storefront variants (editorial | scandi | industrial),
 * switchable via ?v=, floating bar, shared in-memory flows — not production.
 */
(function () {
  const VARIANT_KEYS = ["editorial", "scandi", "industrial"];
  const state = VellanoProto.createState();
  const root = document.getElementById("app");
  const stateEl = document.getElementById("state-panel");
  const switcherEl = document.getElementById("proto-switcher");
  const toastEl = document.getElementById("toast");

  function currentVariant() {
    const params = new URLSearchParams(location.search);
    const v = params.get("v") || params.get("variant") || "editorial";
    return VARIANT_KEYS.includes(v) ? v : "editorial";
  }

  function setVariant(key) {
    const params = new URLSearchParams(location.search);
    params.set("v", key);
    params.delete("variant");
    history.replaceState(null, "", "?" + params.toString() + location.hash);
    render();
  }

  function cycle(dir) {
    const i = VARIANT_KEYS.indexOf(currentVariant());
    const next = VARIANT_KEYS[(i + dir + VARIANT_KEYS.length) % VARIANT_KEYS.length];
    setVariant(next);
  }

  function go(view, productId) {
    state.view = view;
    if (productId !== undefined && productId !== null) {
      if (state.productId !== productId) {
        state.pdpFabric = null;
        state.pdpSize = null;
      }
      state.productId = productId;
    }
    if (view === "home") state.productId = null;
    render();
    window.scrollTo(0, 0);
  }

  function updateLivePrice() {
    const p = VellanoProto.PRODUCTS.find((x) => x.id === state.productId);
    if (!p || state.view !== "product") return;
    const size =
      (root.querySelector("[name=size]:checked") || {}).value || p.defaultSize;
    const el = root.querySelector("[data-live-price]");
    if (el) {
      const price = VellanoProto.fmt(VellanoProto.skuPrice(p, size));
      if (el.tagName === "STRONG" || el.classList.contains("sc-price") || el.classList.contains("ed-price")) {
        el.innerHTML = price + (el.classList.contains("ed-price") ? ' <small>VAT incl.</small>' : "");
      } else {
        el.textContent = price;
      }
    }
  }

  function render() {
    const key = currentVariant();
    const variant = VellanoProto.VARIANTS[key];
    document.body.dataset.variant = key;
    root.innerHTML = variant.render(state);
    VellanoProto.wireCommerce(root, state, go, render);

    // Live price on SKU change without full remount of radios focus loss —
    // wire already re-renders on change; also sync once:
    updateLivePrice();

    stateEl.textContent = JSON.stringify(VellanoProto.stateSnapshot(state), null, 2);

    const label = variant.label;
    switcherEl.querySelector("[data-label]").textContent =
      key.charAt(0).toUpperCase() + " (" + label + ")";

    if (state.toast) {
      toastEl.textContent = state.toast;
      toastEl.hidden = false;
      const msg = state.toast;
      state.toast = null;
      setTimeout(() => {
        if (toastEl.textContent === msg) toastEl.hidden = true;
      }, 2800);
    }

    // Soft-hold ticker
    if (state.checkout.holdStartedAt && state.view === "checkout") {
      clearTimeout(render._holdTimer);
      render._holdTimer = setTimeout(render, 1000);
    }
  }

  switcherEl.querySelector("[data-prev]").addEventListener("click", () => cycle(-1));
  switcherEl.querySelector("[data-next]").addEventListener("click", () => cycle(1));

  document.addEventListener("keydown", (e) => {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target.isContentEditable) return;
    if (e.key === "ArrowLeft") cycle(-1);
    if (e.key === "ArrowRight") cycle(1);
  });

  render();
})();
