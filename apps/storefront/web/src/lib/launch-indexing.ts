import { currentCustomerPolicies } from "./customer-policies";
import { ORGANIZATION_LOGO_PATH } from "./homepage-structured-data";
import { SHOP_CATEGORIES } from "./shop-categories";

const PRIVATE_PREFIXES = ["/account", "/checkout", "/bag", "/sign-in", "/sign-up", "/order", "/api"];

type IndexingEnv = Record<string, string | undefined>;

export function storefrontIndexable(env: IndexingEnv = process.env): boolean {
  // Spec #1000: the whole site stays noindex until the owner's reviewed policy facts exist.
  if (!currentCustomerPolicies()) return false;
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

export const PUBLIC_INFO_PATHS = [
  "/help",
  "/policies/delivery",
  "/policies/returns",
  "/policies/refunds",
  "/policies/terms",
  "/policies/privacy",
  "/policies/paia",
] as const;

const CATEGORY_PATHS: string[] = SHOP_CATEGORIES.map((category) => category.href);

export function catalogueIndexable(pathname: string, env: IndexingEnv = process.env): boolean {
  if (!storefrontIndexable(env)) return false;
  const path = pathOnly(pathname);
  if (isPrivatePath(path)) return false;
  return path === "/" || path === "/shop" || path === "/help" || CATEGORY_PATHS.includes(path) ||
    path.startsWith("/product/") || path.startsWith("/policies/");
}

export function robotsHeader(pathname: string, env: IndexingEnv = process.env): "noindex, nofollow, noarchive" | null {
  const path = pathOnly(pathname);
  const indexable = path === ORGANIZATION_LOGO_PATH || path === "/llms.txt"
    ? storefrontIndexable(env)
    : catalogueIndexable(path, env);
  return indexable ? null : "noindex, nofollow, noarchive";
}

export function sitemapPaths(input: {
  indexable: boolean;
  products: { path: string }[];
}): string[] {
  if (!input.indexable) return [];
  const paths = ["/", "/shop", ...CATEGORY_PATHS, ...PUBLIC_INFO_PATHS];
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
