import type { Metadata } from "next";

type ShareImage = { url: string; alt: string; width?: number; height?: number };
type PublicPage = {
  title: string;
  description?: string;
  path: string;
  absoluteTitle?: boolean;
  image?: ShareImage;
};

const defaultImage: ShareImage = {
  url: "/hero-sofas.jpg",
  alt: "Two pale sofas with round cushions",
  width: 1600,
  height: 1066,
};

export function publicPageMetadata({ title, description, path, absoluteTitle, image = defaultImage }: PublicPage): Metadata {
  return {
    title: absoluteTitle ? { absolute: title } : title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title: absoluteTitle ? title : `${title} | DasKasas`,
      description,
      url: path,
      type: "website",
      siteName: "DasKasas",
      locale: "en_ZA",
      images: [image],
    },
  };
}
