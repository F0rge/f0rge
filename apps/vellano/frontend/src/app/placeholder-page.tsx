type PlaceholderPageProps = {
  title: string;
  comingIn: string;
};

export function PlaceholderPage({ title, comingIn }: PlaceholderPageProps) {
  return (
    <section>
      <h1 className="cds--type-productive-heading-04">{title}</h1>
      <p className="cds--type-body-01">Coming in {comingIn}.</p>
    </section>
  );
}
