"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";

export default function ErrorPage() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  return <section className="content error-state" role="alert"><p className="eyebrow">The Collector</p><h1 ref={heading} tabIndex={-1}>We couldn’t load the collection.</h1><p>Please try again in a moment.</p><button type="button" onClick={() => window.location.reload()}>Try again</button><Link href="/">Return home</Link></section>;
}
