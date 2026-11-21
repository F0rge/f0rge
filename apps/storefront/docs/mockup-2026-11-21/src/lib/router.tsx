import { useEffect, useSyncExternalStore, type ComponentProps } from 'react';
import { findPiece } from '@/content';

const PAGES = ['home', 'shop', 'sofas', 'dining-room', 'on-sale', 'arc', 'bag', 'checkout', 'help'] as const;
type StaticPage = (typeof PAGES)[number];

/** A page: a fixed route or a product page `p-<sku lower-case>`. */
export type Page = StaticPage | `p-${string}`;
/** A link target: a page, optionally with a section id (`help/contact`). */
export type Route = Page | `${Page}/${string}`;

const ALIASES: Record<string, Page> = { delivery: 'help', blocks: 'home' };

function parse(hash: string): { page: Page; section?: string } {
  const [name = '', section] = hash.replace(/^#\/?/, '').split('/');
  if ((PAGES as readonly string[]).includes(name)) return { page: name as Page, section };
  if (ALIASES[name]) return { page: ALIASES[name], section };
  if (findPiece(name)) return { page: name as Page, section };
  return { page: 'home' };
}

const readHash = () => window.location.hash;

function subscribe(cb: () => void) {
  window.addEventListener('hashchange', cb);
  return () => window.removeEventListener('hashchange', cb);
}

/** Current page; unknown hashes resolve to "home", `#delivery` to "help". */
export function useRoute(): Page {
  return parse(useSyncExternalStore(subscribe, readHash, () => '')).page;
}

/**
 * Call once, in the shell: scrolls to the section named in the hash, else to the top.
 * Runs after the page has rendered, so the section exists.
 */
export function useScrollOnNavigate() {
  const hash = useSyncExternalStore(subscribe, readHash, () => '');
  // Braces matter: newer browsers return a Promise from scrollTo, and React would call it as a cleanup.
  useEffect(() => {
    const { section } = parse(hash);
    const el = section ? document.getElementById(section) : null;
    if (el) {
      el.scrollIntoView();
    } else {
      window.scrollTo(0, 0);
    }
  }, [hash]);
}

export function navigate(to: Route) {
  window.location.hash = to;
}

type LinkProps = Omit<ComponentProps<'a'>, 'href'> & { to: Route };

/** `<Link to="arc">` renders `<a href="#arc">`; works inside `<Button asChild>`. */
export function Link({ to, ...props }: LinkProps) {
  return <a href={`#${to}`} {...props} />;
}
