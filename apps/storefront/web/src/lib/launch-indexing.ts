const PRIVATE_PREFIXES = ["/account", "/checkout", "/bag", "/sign-in", "/sign-up", "/order", "/api", "/study"];

type IndexingEnv = Record<string, string | undefined>;

export function storefrontIndexable(env: IndexingEnv = process.env): boolean {
  if (env.STOREFRONT_INDEXING_ENABLED !== "true") return false;
  if (env.RAILWAY_ENVIRONMENT_NAME !== "production") return false;
  if (env.STOREFRONT_PRIVATE_PREVIEW !== "off") return false;
  try {
    return new URL(env.NEXT_PUBLIC_BASE_URL || "").protocol === "https:";
  } catch {
    return false;
  }
}

function pathOnly(pathname: string): string {
  return (pathname.split("?")[0] || "/").replace(/\/+$/, "") || "/";
}

function isPrivatePath(path: string): boolean {
  return PRIVATE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

export function catalogueIndexable(pathname: string, env: IndexingEnv = process.env): boolean {
  if (!storefrontIndexable(env)) return false;
  const path = pathOnly(pathname);
  if (isPrivatePath(path)) return false;
  return path === "/" || path === "/shop" || path === "/collections" || path === "/support" ||
    path.startsWith("/product/") || path.startsWith("/policies/");
}

export function robotsHeader(pathname: string, env: IndexingEnv = process.env): "noindex, nofollow, noarchive" | null {
  return catalogueIndexable(pathname, env) ? null : "noindex, nofollow, noarchive";
}

export function sitemapPaths(input: {
  indexable: boolean;
  products: { path: string }[];
  collections: { handle: string }[];
}): string[] {
  if (!input.indexable) return [];
  const paths = [
    "/",
    "/shop",
    "/collections",
    "/support",
    "/policies/delivery",
    "/policies/returns",
    "/policies/privacy",
  ];
  input.collections.forEach((collection) => {
    paths.push(`/shop?collection=${encodeURIComponent(collection.handle)}`);
  });
  input.products.forEach((product) => {
    if (product.path.startsWith("/product/")) paths.push(product.path);
  });
  return paths.filter((path) => {
    const bare = pathOnly(path);
    return !isPrivatePath(bare);
  });
}

export function canonicalUrl(baseUrl: string, path: string): string {
  const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
  return new URL(path, base).toString();
}
