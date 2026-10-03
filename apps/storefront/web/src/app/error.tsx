"use client";

import Link from "next/link";

export default function ErrorPage() {
  return <section className="content error-state" role="alert"><p className="eyebrow">The Collector</p><h1>We couldn’t load the collection.</h1><p>Please try again in a moment.</p><button type="button" onClick={() => window.location.reload()}>Try again</button><Link href="/">Return home</Link></section>;
}
