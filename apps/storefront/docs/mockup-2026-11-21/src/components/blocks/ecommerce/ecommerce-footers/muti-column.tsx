import type { ReactNode } from 'react';
import { Link, type Route } from '@/lib/router';

interface FooterLink {
  label: string;
  to: Route;
}

export interface EcommerceFooterMultiColumnProps {
  brand: ReactNode;
  blurb: string;
  /** Plain link columns. */
  columns: { title: string; links: FooterLink[] }[];
  /** The block's "Follow Us" column, used for the showroom details (plain text, no links). */
  visit: { title: string; lines: string[] };
  bottomLinks: FooterLink[];
  copyright: string;
}

export default function EcommerceFooterMultiColumn({
  brand,
  blurb,
  columns,
  visit,
  bottomLinks,
  copyright,
}: EcommerceFooterMultiColumnProps) {

  return (
    <footer className="bg-muted/50 border-t px-4 py-8 md:py-12">
      <div className="container mx-auto max-w-7xl">
        {/* Brand Section */}
        <div className="mb-8 md:mb-12">
          <Link to="home" className="inline-block">
            <h2 className="text-foreground text-2xl font-bold">{brand}</h2>
          </Link>
          <p className="text-muted-foreground mt-2 max-w-md text-sm">{blurb}</p>
        </div>

        {/* Footer Links Grid */}
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {columns.map((column) => (
            <div key={column.title} className="space-y-4">
              <h3 className="text-foreground text-sm font-semibold tracking-wider uppercase">
                {column.title}
              </h3>
              <ul className="space-y-3">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <Link
                      to={link.to}
                      className="text-muted-foreground hover:text-foreground text-sm transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* Follow Us: here, the showroom */}
          <div className="space-y-4">
            <h3 className="text-foreground text-sm font-semibold tracking-wider uppercase">
              {visit.title}
            </h3>
            <div className="space-y-4">
              <ul className="space-y-3">
                {visit.lines.map((line) => (
                  <li key={line} className="text-muted-foreground text-sm">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="border-border mt-8 border-t pt-8">
          <div className="flex flex-col space-y-4 md:flex-row md:items-center md:justify-between md:space-y-0">
            <div className="flex flex-col space-y-2 md:flex-row md:space-y-0 md:space-x-6">
              {bottomLinks.map((link) => (
                <Link
                  key={link.label}
                  to={link.to}
                  className="text-muted-foreground hover:text-foreground text-xs transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
            <p className="text-muted-foreground text-xs">{copyright}</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
