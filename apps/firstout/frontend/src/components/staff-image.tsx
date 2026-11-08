"use client";
import { useEffect, useState, type ImgHTMLAttributes } from "react";
import { staffFetch } from "@/lib/staff-fetch";

/** Protected media uses the same fresh organisation token as JSON requests. */
export function StaffImage({src, alt, ...props}: Omit<ImgHTMLAttributes<HTMLImageElement>, "src"> & {src: string}) {
  const [image, setImage] = useState<{source: string; url: string} | null>(null);
  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    const controller = new AbortController();
    void staffFetch(src, {signal: controller.signal}).then(async response => {
      if (!response.ok) throw new Error("Image unavailable");
      const blob = await response.blob();
      if (!active) return;
      objectUrl = URL.createObjectURL(blob);
      setImage({source: src, url: objectUrl});
    }).catch(() => { /* Unavailable protected images stay hidden. */ });
    return () => { active = false; controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [src]);
  if (image?.source !== src) return null;
  // Blob URLs are authenticated locally and cannot use the Next image optimizer.
  // eslint-disable-next-line @next/next/no-img-element
  return <img {...props} src={image.url} alt={alt ?? ""} />;
}
