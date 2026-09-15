import { ButtonLink } from "@/components/button";

export default function NotFound() {
  return (
    <section className="mx-auto w-full max-w-2xl px-4 py-24">
      <p className="eyebrow">404</p>
      <h1 className="type-display mt-4 text-[2.25rem] sm:text-[3.375rem]">This URL is not a workspace and not a page.</h1>
      <p className="mt-4 text-base text-muted">If you were looking for a company hostname, it may not be provisioned yet.</p>
      <div className="mt-8">
        <ButtonLink href="/">Back to the product site</ButtonLink>
      </div>
    </section>
  );
}
