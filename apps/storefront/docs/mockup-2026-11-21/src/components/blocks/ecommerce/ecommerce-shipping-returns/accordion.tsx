import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

interface Heading {
  title: string;
  subtitle: string;
}
interface PointList {
  title: string;
  points: string[];
}
interface Step {
  title: string;
  description: string;
}
interface Callout {
  title: string;
  description: string;
}

export interface ShippingReturnsAccordionProps {
  title: string;
  description: string;
  delivery: Heading & { columns: [PointList, PointList]; note: string };
  timing: Heading & { steps: [Step, Step, Step]; callout: Callout };
  returns: Heading & {
    returnable: PointList;
    nonReturnable: PointList;
    processTitle: string;
    steps: [Step, Step, Step];
    callout: Callout;
  };
}

export default function ShippingReturnsAccordion({
  title,
  description,
  delivery,
  timing,
  returns,
}: ShippingReturnsAccordionProps) {
  return (
    <div className="px-4 py-8 md:py-12">
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
            {title}
          </h2>
          <p className="text-muted-foreground mt-2">{description}</p>
        </div>

        <Accordion type="single" collapsible className="w-full space-y-4">
          <AccordionItem
            value="shipping-details"
            className="rounded-lg border px-6 py-2"
          >
            <AccordionTrigger className="py-6 text-left hover:no-underline">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 flex h-10 w-10 items-center justify-center rounded-full">
                  <svg
                    className="text-primary h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{delivery.title}</h3>
                  <p className="text-muted-foreground text-sm">
                    {delivery.subtitle}
                  </p>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pt-2 pb-6">
              <div className="space-y-6 text-sm">
                <div className="grid gap-4 md:grid-cols-2">
                  {delivery.columns.map((column) => (
                    <div key={column.title} className="space-y-3">
                      <h4 className="font-medium">{column.title}</h4>
                      <ul className="text-muted-foreground space-y-2">
                        {column.points.map((point) => (
                          <li key={point}>• {point}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                <div className="bg-muted/50 rounded-lg p-4">
                  <p className="text-sm">
                    <strong>Note:</strong> {delivery.note}
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem
            value="estimated-delivery"
            className="rounded-lg border px-6 py-2"
          >
            <AccordionTrigger className="py-6 text-left hover:no-underline">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 flex h-10 w-10 items-center justify-center rounded-full">
                  <svg
                    className="text-primary h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{timing.title}</h3>
                  <p className="text-muted-foreground text-sm">
                    {timing.subtitle}
                  </p>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pt-2 pb-6">
              <div className="space-y-6 text-sm">
                <div className="grid gap-6 md:grid-cols-3">
                  <div className="text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-100 text-green-600">
                      <span className="font-bold">1</span>
                    </div>
                    <h4 className="mb-2 font-medium">{timing.steps[0].title}</h4>
                    <p className="text-muted-foreground">
                      {timing.steps[0].description}
                    </p>
                  </div>
                  <div className="text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600">
                      <span className="font-bold">2</span>
                    </div>
                    <h4 className="mb-2 font-medium">{timing.steps[1].title}</h4>
                    <p className="text-muted-foreground">
                      {timing.steps[1].description}
                    </p>
                  </div>
                  <div className="text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-purple-100 text-purple-600">
                      <span className="font-bold">3</span>
                    </div>
                    <h4 className="mb-2 font-medium">{timing.steps[2].title}</h4>
                    <p className="text-muted-foreground">
                      {timing.steps[2].description}
                    </p>
                  </div>
                </div>
                <div className="border-primary bg-primary/5 rounded-lg border-l-4 p-4">
                  <h4 className="mb-2 font-medium">{timing.callout.title}</h4>
                  <p className="text-muted-foreground">
                    {timing.callout.description}
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem
            value="return-policy"
            className="rounded-lg border px-6 py-2 last:border-b"
          >
            <AccordionTrigger className="py-6 text-left hover:no-underline">
              <div className="flex items-center gap-3">
                <div className="bg-primary/10 flex h-10 w-10 items-center justify-center rounded-full">
                  <svg
                    className="text-primary h-5 w-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
                    />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold">{returns.title}</h3>
                  <p className="text-muted-foreground text-sm">
                    {returns.subtitle}
                  </p>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="pt-2 pb-6">
              <div className="space-y-6 text-sm">
                <div className="grid gap-6 md:grid-cols-2">
                  <div>
                    <h4 className="mb-3 font-medium text-green-600">
                      ✓ {returns.returnable.title}
                    </h4>
                    <ul className="text-muted-foreground space-y-2">
                      {returns.returnable.points.map((point) => (
                        <li key={point}>• {point}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="mb-3 font-medium text-red-600">
                      ✗ {returns.nonReturnable.title}
                    </h4>
                    <ul className="text-muted-foreground space-y-2">
                      {returns.nonReturnable.points.map((point) => (
                        <li key={point}>• {point}</li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="font-medium">{returns.processTitle}</h4>
                  <div className="grid gap-4 md:grid-cols-3">
                    {returns.steps.map((step, i) => (
                      <div
                        key={step.title}
                        className="bg-muted/30 rounded-lg p-4 text-center"
                      >
                        <div className="mb-2 font-medium">
                          {i + 1}. {step.title}
                        </div>
                        <p className="text-muted-foreground text-xs">
                          {step.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                  <h4 className="mb-2 font-medium text-blue-900">
                    {returns.callout.title}
                  </h4>
                  <p className="text-sm text-blue-800">
                    {returns.callout.description}
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </div>
  );
}
