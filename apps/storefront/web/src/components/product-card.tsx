"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Image from "next/image";
import { Button, cn } from "@f0rge/ui";
import { TrackedProductLink } from "./analytics/tracked-product-link";
import { PieceImage } from "./piece-image";
import { cardAlert, finishChoices, startVariant, type CardAlert } from "@/lib/card-alert";
import type { ListedPiece } from "@/lib/medusa";
import { formatZar } from "@/lib/order-money";
import { variantHref } from "@/lib/shop-filters";

// One observer marks cards as seen so their alert bar and struck price animate in (CSS in app/style.css).
// <html data-card-motion> is what hides them until then, so a failed bundle or no IntersectionObserver leaves them visible.
let seenObserver: IntersectionObserver | undefined;
function watchSeen(card: HTMLElement) {
  if (typeof IntersectionObserver === "undefined" || matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
  document.documentElement.setAttribute("data-card-motion", "");
  seenObserver ??= new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting).forEach((entry, index) => {
      (entry.target as HTMLElement).style.setProperty("--card-delay", `${index * 0.08}s`);
      entry.target.setAttribute("data-seen", "");
      seenObserver?.unobserve(entry.target);
    });
  }, { threshold: 0.35 });
  seenObserver.observe(card);
  return () => seenObserver?.unobserve(card);
}

const Spark = () => <svg data-alert-spark viewBox="0 0 10 10" aria-hidden="true" className="size-[9px] shrink-0 text-gold-deep md:size-2.5">
  <path fill="currentColor" d="M5 0 6 4 10 5 6 6 5 10 4 6 0 5 4 4z" />
</svg>;

function AlertMessage({ alert }: { alert: CardAlert }) {
  if (alert.kind === "just-arrived") return <><Spark />Just arrived</>;
  if (alert.kind === "made-to-order") return <>Made to order</>;
  const lines = [`${alert.percent}% off`, `Save ${alert.saving}`, `${alert.percent}% off`];
  return <>
    <span className="sr-only">{alert.percent}% off, save {alert.saving}</span>
    <span aria-hidden="true" className="block h-4 overflow-hidden leading-4">
      {lines.map((line, index) => <span key={index} data-alert-roll className="block">{line}</span>)}
    </span>
  </>;
}

function PhotoCount({ count, position, dark, inBar }: { count: number; position: number; dark: boolean; inBar: boolean }) {
  if (count < 2) return null;
  return <span aria-hidden="true" className={cn("pointer-events-none flex gap-[3px]",
    !inBar && "absolute bottom-2.5 left-1/2 -translate-x-1/2 gap-1 rounded-full bg-background/90 px-[7px] py-[5px] shadow-[0_1px_3px_rgb(0_0_0/.12)]")}>
    {Array.from({ length: count }, (_, index) => <span key={index} className={cn("h-[3px] rounded-full transition-[width,background-color]",
      inBar ? "w-2" : "w-3.5", index === position && (inBar ? "w-3.5" : "w-[22px]"),
      dark ? (index === position ? "bg-gold" : "bg-white/30") : (index === position ? "bg-foreground" : "bg-foreground/20"))} />)}
  </span>;
}

function Photos({ piece, images, href, alert, eager }: { piece: ListedPiece; images: string[]; href: string; alert: CardAlert | null; eager: boolean }) {
  const track = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; left: number; moved: boolean } | null>(null);
  const dragged = useRef(false);
  const [position, setPosition] = useState(0);
  // Announced only after the shopper moves; nothing scrolls the track on its own.
  const [announcement, setAnnouncement] = useState("");
  const multiple = images.length > 1;
  const dark = alert?.kind === "sale";

  function go(index: number) {
    const element = track.current;
    if (!element?.clientWidth) return;
    element.style.scrollBehavior = "";
    element.scrollTo({ left: Math.max(0, Math.min(images.length - 1, index)) * element.clientWidth });
  }
  const step = (direction: number) => go(Math.round((track.current?.scrollLeft ?? 0) / (track.current?.clientWidth || 1)) + direction);

  // Mouse drag swipes like touch; touch and trackpads use native scrolling and snap.
  function endDrag(clientX: number) {
    const current = drag.current;
    const element = track.current;
    drag.current = null;
    if (!current?.moved || !element) return;
    dragged.current = true;
    setTimeout(() => { dragged.current = false; }, 0);
    element.style.scrollSnapType = "";
    const width = element.clientWidth;
    const dx = clientX - current.x;
    go(Math.abs(dx) > width * 0.15 ? Math.round((element.scrollLeft - Math.sign(dx) * width * 0.35) / width) : Math.round(element.scrollLeft / width));
  }

  const link = (children: ReactNode, className: string) => <TrackedProductLink href={href} productId={piece.id} impression={false}
    draggable={false} aria-label={`${piece.title}${multiple ? `, ${images.length} photos` : ""}`} className={cn("outline-none", className)}>
    {children}
  </TrackedProductLink>;

  return <>
    {images.length === 0
      ? link(<PieceImage product={{ title: piece.title }} />, "block size-full")
      : <div
        ref={track}
        className="flex size-full snap-x snap-mandatory overflow-x-auto overscroll-x-contain [scrollbar-width:none] motion-safe:scroll-smooth [&::-webkit-scrollbar]:hidden"
        onScroll={(event) => {
          const element = event.currentTarget;
          if (!element.clientWidth) return;
          const next = Math.round(element.scrollLeft / element.clientWidth);
          if (next === position) return;
          setPosition(next);
          setAnnouncement(`Photo ${next + 1} of ${images.length}`);
        }}
        onKeyDown={(event) => {
          if (!multiple || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
          event.preventDefault();
          step(event.key === "ArrowLeft" ? -1 : 1);
        }}
        onPointerDown={(event) => {
          if (!multiple || event.pointerType !== "mouse" || event.button !== 0) return;
          drag.current = { x: event.clientX, left: event.currentTarget.scrollLeft, moved: false };
        }}
        onPointerMove={(event) => {
          const current = drag.current;
          if (!current) return;
          const dx = event.clientX - current.x;
          const element = event.currentTarget;
          if (!current.moved && Math.abs(dx) > 5) {
            current.moved = true;
            element.setPointerCapture(event.pointerId);
            element.style.scrollSnapType = "none";
            element.style.scrollBehavior = "auto";
          }
          if (current.moved) element.scrollLeft = current.left - dx;
        }}
        onPointerUp={(event) => endDrag(event.clientX)}
        onPointerCancel={(event) => endDrag(event.clientX)}
        onClickCapture={(event) => {
          if (!dragged.current) return;
          event.preventDefault();
          event.stopPropagation();
        }}
      >
        {link(images.map((url, index) => <Image key={url} src={url} alt={`${piece.title}, photo ${index + 1} of ${images.length}`}
          unoptimized loading={eager && index === 0 ? "eager" : "lazy"} fetchPriority={index > 0 ? "low" : eager ? "high" : undefined} draggable={false} width={800} height={1000}
          className="size-full flex-none snap-start snap-always object-contain select-none" />), "flex size-full cursor-pointer")}
      </div>}
    {multiple && <span aria-live="polite" className="sr-only">{announcement}</span>}
    {alert && <div data-alert-bar className={cn(
      "pointer-events-none absolute inset-x-2 bottom-2 flex h-[30px] items-center justify-between gap-2 rounded-[calc(var(--radius)*.8)] px-2.5 text-[11px] font-semibold tracking-[.02em] shadow-[0_2px_10px_rgb(0_0_0/.08)] backdrop-blur-md backdrop-saturate-[1.3] md:inset-x-3 md:bottom-3 md:h-9 md:px-3 md:text-xs",
      dark ? "bg-primary/80 text-gold" : "bg-background/75 text-foreground")}>
      <span className="inline-flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap"><AlertMessage alert={alert} /></span>
      <PhotoCount count={images.length} position={position} dark={dark} inBar />
    </div>}
    {!alert && <PhotoCount count={images.length} position={position} dark={false} inBar={false} />}
    {multiple && ([-1, 1] as const).map((direction) => {
      const end = direction < 0 ? position === 0 : position === images.length - 1;
      return <Button key={direction} type="button" variant="outline" size="icon" aria-disabled={end}
        aria-label={`${direction < 0 ? "Previous" : "Next"} photo of ${piece.title}`} onClick={() => step(direction)}
        className={cn("absolute top-[calc(50%-1rem)] hidden rounded-full bg-background/90 opacity-0 transition-opacity pointer-fine:inline-flex group-hover/media:opacity-100 group-focus-within/media:opacity-100 aria-disabled:text-muted-foreground",
          direction < 0 ? "left-2.5" : "right-2.5")}>
        {direction < 0 ? <ChevronLeft aria-hidden /> : <ChevronRight aria-hidden />}
      </Button>;
    })}
  </>;
}

/** The shop card (approved design E2 · Caption): photo with an optional alert bar, finish dots, then name and price. */
export function ProductCard({ piece, initialVariantId, featured = false, eager = false }: {
  piece: ListedPiece;
  initialVariantId?: string;
  featured?: boolean;
  /** Load the first photo eagerly: cards in the first row. */
  eager?: boolean;
}) {
  const card = useRef<HTMLLIElement>(null);
  const start = startVariant(piece, initialVariantId);
  // The shopper's finish choice, by id, so a new filter result neither remounts the card nor loses the choice.
  const [chosen, setChosen] = useState<string>();
  const shown = piece.variants.find(({ id }) => id === chosen) ?? start;
  useEffect(() => {
    if (card.current) return watchSeen(card.current);
  }, []);

  const finishes = finishChoices(piece);
  const alert = cardAlert(piece, shown);
  const sale = alert?.kind === "sale";
  const changed = shown?.id !== start?.id;
  const productHref = piece.href.split("?")[0];
  // The product page starts on the first variant when the URL has no selection.
  const href = shown && shown.id !== piece.variants[0]?.id ? variantHref(productHref, shown.id) : productHref;
  const nameLink = <TrackedProductLink href={href} productId={piece.id} className="underline-offset-3 hover:underline">{piece.title}</TrackedProductLink>;

  return <li ref={card} data-product-card className={cn("min-w-0", featured && "col-span-full md:grid md:grid-cols-[2fr_3fr] md:items-center md:gap-10")}>
    <div className="group/media relative aspect-[4/5] overflow-hidden rounded-[var(--radius)] bg-muted has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-ring">
      <Photos key={shown?.id} piece={piece} images={shown?.images ?? []} href={href} alert={alert} eager={eager} />
      {finishes.length > 0 && <div role="group" aria-label={`Finishes of ${piece.title}`} className="absolute top-2 right-2 flex rounded-full bg-background/90 px-[3px] py-px shadow-[0_1px_3px_rgb(0_0_0/.12)] md:top-3 md:right-3 md:px-1 md:py-0.5">
        {finishes.map(({ swatch, name, variant }) => <button key={swatch} type="button" aria-pressed={shown?.swatch === swatch} aria-label={name} title={name}
          style={{ "--swatch": swatch } as CSSProperties} onClick={() => setChosen(variant.id)}
          className="relative size-6 cursor-pointer rounded-full before:absolute before:inset-[5px] before:rounded-full before:bg-(--swatch) before:shadow-[inset_0_0_0_1px_rgb(0_0_0/.15)] focus-visible:outline-2 focus-visible:outline-ring aria-pressed:before:inset-1.5 aria-pressed:before:shadow-[inset_0_0_0_1px_rgb(0_0_0/.15),0_0_0_1.5px_#fff,0_0_0_2.75px_var(--foreground)]" />)}
      </div>}
    </div>
    <div className={cn("grid gap-0.5 pt-2.5 md:pt-3.5", featured && "md:gap-2 md:pt-0")}>
      <h3 className={cn("line-clamp-2 text-[15px]/5 font-medium md:text-base/6", featured && "md:text-2xl/8")}>{nameLink}</h3>
      <p className={cn("flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm/5 tabular-nums md:text-[15px]/[22px]", featured && "md:text-lg")}>
        {sale && shown?.was != null
          ? <><span className="font-semibold"><span className="sr-only">Now </span>{shown.priceLabel}</span>
            <s data-strike className="relative text-[.9em] text-muted-foreground no-underline after:absolute after:inset-x-[-1px] after:top-[52%] after:h-px after:origin-left after:bg-current">
              <span className="sr-only">Was </span>{formatZar(shown.was)}
            </s></>
          : <span className="font-medium">{changed && shown ? shown.priceLabel : piece.priceLabel}</span>}
      </p>
      {href !== productHref && <TrackedProductLink href={productHref} productId={piece.id} impression={false} prefetch={false}
        aria-label={`View all options for ${piece.title}`}
        className="inline-flex min-h-6 w-fit items-center text-sm text-muted-foreground underline underline-offset-3 hover:text-foreground">
        View all options
      </TrackedProductLink>}
      {featured && <TrackedProductLink href={href} productId={piece.id} impression={false}
        className="mt-4 hidden h-9 w-1/2 items-center justify-center rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 md:inline-flex">
        View piece
      </TrackedProductLink>}
    </div>
  </li>;
}
