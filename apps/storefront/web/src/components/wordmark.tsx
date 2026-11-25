import Image, { type ImageProps } from "next/image";

export function BrandMark({ className, loading }: Pick<ImageProps, "className" | "loading">) {
  return <Image src="/brand/dk-champagne.png" alt="" width={384} height={203} unoptimized className={className} loading={loading} />;
}

export function Wordmark() {
  return <Image src="/brand/daskasas-geometric.png" alt="" width={760} height={105} unoptimized className="h-auto w-full" />;
}
