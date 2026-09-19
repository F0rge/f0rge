window.VellanoProto = window.VellanoProto || {};

VellanoProto.filteredProducts = function (state) {
  const q = (state.search || "").trim().toLowerCase();
  return VellanoProto.PRODUCTS.filter((p) => {
    if (state.collection !== "All" && p.collection !== state.collection) return false;
    if (!q) return true;
    return (
      p.name.toLowerCase().includes(q) ||
      p.collection.toLowerCase().includes(q) ||
      p.blurb.toLowerCase().includes(q)
    );
  });
};

VellanoProto.collections = function () {
  const set = new Set(VellanoProto.PRODUCTS.map((p) => p.collection));
  return ["All", ...Array.from(set)];
};

VellanoProto.swatch = function (hue, label) {
  return (
    '<div class="swatch" style="--hue:' +
    hue +
    '" aria-hidden="true"><span>' +
    (label || "").slice(0, 2).toUpperCase() +
    "</span></div>"
  );
};

VellanoProto.el = function (html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
};

VellanoProto.bindNav = function (root, state, go) {
  root.querySelectorAll("[data-go]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const view = btn.getAttribute("data-go");
      const pid = btn.getAttribute("data-product");
      go(view, pid || null);
    });
  });
  root.querySelectorAll("[data-search]").forEach((inp) => {
    inp.addEventListener("input", () => {
      state.search = inp.value;
      go(state.view, state.productId);
    });
  });
  root.querySelectorAll("[data-collection]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.collection = btn.getAttribute("data-collection");
      go("home");
    });
  });
};

VellanoProto.holdRemaining = function (state) {
  if (!state.checkout.holdStartedAt) return null;
  const end =
    state.checkout.holdStartedAt + state.checkout.holdMinutes * 60 * 1000;
  const ms = Math.max(0, end - Date.now());
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return m + ":" + String(s).padStart(2, "0");
};
