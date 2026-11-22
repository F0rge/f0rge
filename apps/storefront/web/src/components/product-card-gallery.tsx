"use client";

import { useId, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Image from "next/image";
import { Button } from "@f0rge/ui";
import { PieceImage } from "./piece-image";

export function ProductCardGallery({ title, images }: { title: string; images: string[] }) {
  const track = useRef<HTMLDivElement>(null);
  const trackId = useId();
  const [position, setPosition] = useState(0);
  const multiple = images.length > 1;

  function advance(direction: number) {
    const element = track.current;
    if (!element?.clientWidth) return;
    const current = Math.round(element.scrollLeft / element.clientWidth);
    const next = Math.max(0, Math.min(images.length - 1, current + direction));
    element.scrollTo({ left: next * element.clientWidth });
  }

  const photoPosition = Math.min(position, images.length - 1);
  return <div className="min-w-0" role={multiple ? "group" : undefined} aria-label={multiple ? `Photos of ${title}` : undefined}>
    {images.length === 0 ? (
      <div className="aspect-square bg-muted"><PieceImage product={{ title }} /></div>
    ) : (
      <div
        id={trackId}
        ref={track}
        className="flex aspect-square snap-x snap-mandatory overflow-x-auto overscroll-x-contain bg-muted [scrollbar-width:none] [&::-webkit-scrollbar]:hidden focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        tabIndex={multiple ? 0 : undefined}
        aria-label={multiple ? `Browse photos of ${title} with the arrow keys` : undefined}
        onScroll={(event) => {
          const element = event.currentTarget;
          if (element.clientWidth) setPosition(Math.max(0, Math.round(element.scrollLeft / element.clientWidth)));
        }}
        onKeyDown={(event) => {
          if (!multiple || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
          event.preventDefault();
          advance(event.key === "ArrowLeft" ? -1 : 1);
        }}
      >
        {images.map((url, index) => <Image key={url} src={url} alt={`${title}, photo ${index + 1} of ${images.length}`}
          unoptimized loading="lazy" draggable={false} width={800} height={800}
          className="h-full w-full flex-none snap-start snap-always object-contain select-none" />)}
      </div>
    )}
    {multiple && <div className="flex items-center justify-between border-b px-2">
      <Button type="button" variant="ghost" size="icon" className="size-11" aria-label={`Previous photo of ${title}`}
        aria-controls={trackId} aria-disabled={photoPosition === 0} onClick={() => advance(-1)}>
        <ChevronLeft aria-hidden />
      </Button>
      <span aria-live="polite" className="text-xs tabular-nums text-muted-foreground">{photoPosition + 1} of {images.length}</span>
      <Button type="button" variant="ghost" size="icon" className="size-11" aria-label={`Next photo of ${title}`}
        aria-controls={trackId} aria-disabled={photoPosition === images.length - 1} onClick={() => advance(1)}>
        <ChevronRight aria-hidden />
      </Button>
    </div>}
  </div>;
}
