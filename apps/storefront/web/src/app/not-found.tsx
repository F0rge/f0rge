import Link from "next/link";

export default function NotFound() {
  return (
    <section className="content error-state" data-storefront-not-found>
      <h1>We can’t find this piece.</h1>
      <p>It may have moved or is no longer available.</p>
      <Link href="/shop" className="text-link">Explore all pieces →</Link>
    </section>
  );
}
