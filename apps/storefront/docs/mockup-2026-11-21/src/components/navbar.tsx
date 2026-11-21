// Original (shadcn/ui): no free navbar block exists, so this is plain shadcn parts.
import { Menu, ShoppingBag } from 'lucide-react';
import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { nav } from '@/content';
import { useBag } from '@/lib/bag';
import { Link, useRoute } from '@/lib/router';
import { cn } from '@/lib/utils';

export function Wordmark({ className }: { className?: string }) {
  return <span className={cn('font-serif font-normal tracking-normal', className)}>DasKasas</span>;
}

export function Navbar() {
  const route = useRoute();
  const { count, setDrawerOpen } = useBag();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      className="bg-background/95 supports-[backdrop-filter]:bg-background/80 sticky z-30 border-b backdrop-blur"
      style={{ top: 'env(safe-area-inset-top, 0px)' }}
    >
      <div className="container mx-auto flex h-16 items-center gap-4 px-4 md:px-6 2xl:max-w-[1400px]">
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
              <Menu className="size-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left">
            <SheetHeader>
              <SheetTitle>
                <Wordmark className="text-2xl" />
              </SheetTitle>
            </SheetHeader>
            <nav className="grid gap-1 px-4">
              {nav.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  onClick={() => setMenuOpen(false)}
                  aria-current={route === item.to ? 'page' : undefined}
                  className="hover:bg-muted aria-[current=page]:bg-muted rounded-md px-3 py-2 text-sm font-medium"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </SheetContent>
        </Sheet>

        <Link to="home" className="text-2xl leading-none" aria-label="DasKasas home">
          <Wordmark />
        </Link>

        <nav className="ml-6 hidden items-center gap-6 md:flex">
          {nav.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-current={route === item.to ? 'page' : undefined}
              className="text-muted-foreground hover:text-foreground aria-[current=page]:text-foreground text-sm font-medium transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <Button
          variant="outline"
          size="icon"
          className="relative ml-auto"
          onClick={() => setDrawerOpen(true)}
          aria-label={`Open bag, ${count} ${count === 1 ? 'item' : 'items'}`}
        >
          <ShoppingBag className="size-5" />
          {count > 0 && (
            <Badge className="absolute -top-2 -right-2 flex h-5 min-w-5 items-center justify-center px-1">
              {count}
            </Badge>
          )}
        </Button>
      </div>
    </header>
  );
}
