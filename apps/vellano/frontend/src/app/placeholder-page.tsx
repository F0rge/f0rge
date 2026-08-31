type PlaceholderPageProps = {
  title: string;
};

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section>
      <h1 className="cds--type-productive-heading-04">{title}</h1>
      <p className="cds--type-body-01">Placeholder. This section is out of scope for S0.</p>
    </section>
  );
}
