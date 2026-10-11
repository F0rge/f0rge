"use client";

import { Button } from "@f0rge/ui";
import { useEffect, useRef } from "react";
import Link from "next/link";

export default function ErrorPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  return <section className="content error-state" role="alert"><p className="eyebrow">Vellano</p><h1 ref={heading} tabIndex={-1}>We couldn’t load the collection.</h1><p>Please try again in a moment.</p><Button type="button" onClick={() => window.location.reload()}>Try again</Button><Link href="/">Return home</Link></section>;
}
