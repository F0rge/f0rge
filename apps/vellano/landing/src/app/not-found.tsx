import { ButtonLink } from "@/components/button";

export default function NotFound() {
  return (
    <section className="mx-auto max-w-2xl px-5 py-28 sm:px-8">
      <p className="eyebrow">404</p>
      <h1 className="mt-4 text-4xl sm:text-5xl">Nothing on this shelf.</h1>
      <p className="mt-4 text-lg text-muted">The page you asked for does not exist.</p>
      <div className="mt-8">
        <ButtonLink href="/">Back home</ButtonLink>
      </div>
    </section>
  );
}
