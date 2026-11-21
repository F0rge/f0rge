import { cn } from '@/lib/utils';

interface PhotoProps {
  src: string;
  alt: string;
  /** Pass the block's own <img> className through unchanged. */
  className?: string;
  width?: number;
  height?: number;
  /** CSS object-position, to show a different part of the same photograph. */
  position?: string;
}

/**
 * One of the three Arc photographs (files in public/, referenced relatively so the
 * build is relocatable). `size-full object-cover` stands in for the Next.js
 * `fill` images the blocks were written for; the block's className wins.
 */
export function Photo({ src, alt, className, width = 1536, height = 1024, position }: PhotoProps) {
  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      style={position ? { objectPosition: position } : undefined}
      className={cn('size-full object-cover', className)}
    />
  );
}

/** Flat muted tile for every image that does not exist yet. */
export function Placeholder({ label, className }: { label: string; className?: string }) {
  return (
    <div
      role="img"
      aria-label={label}
      className={cn(
        'bg-muted flex size-full min-h-24 items-center justify-center p-4 text-center',
        className,
      )}
    >
      <span className="text-muted-foreground text-xs">{label}</span>
    </div>
  );
}

/** A block image slot: the photo if one exists, otherwise a Placeholder with the same classes. */
export function ImageSlot({
  photo,
  placeholder,
  className,
}: {
  photo?: { src: string; alt: string; position?: string };
  placeholder: string;
  className?: string;
}) {
  return photo ? (
    <Photo src={photo.src} alt={photo.alt} position={photo.position} className={className} />
  ) : (
    <Placeholder label={placeholder} className={className} />
  );
}
