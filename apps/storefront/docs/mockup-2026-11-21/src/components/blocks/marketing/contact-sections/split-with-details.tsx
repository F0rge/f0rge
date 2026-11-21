import { useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Mail, MapPin, Phone } from 'lucide-react';

interface Detail {
  title: string;
  description: string;
  value: ReactNode;
}

export interface SplitWithDetailsProps {
  title: string;
  description: string;
  formTitle: string;
  submitLabel: string;
  /** Root id, for #help/contact links. */
  id?: string;
  /** Shown in place of formNote after submit; nothing is sent. */
  submittedNote: string;
  address: Detail;
  email: Detail;
  phone: Detail;
}

export default function SplitWithDetails({
  title,
  description,
  formTitle,
  submitLabel,
  id,
  submittedNote,
  address,
  email,
  phone,
}: SplitWithDetailsProps) {
  const [submitted, setSubmitted] = useState(false);

  return (
    <div id={id} className="container mx-auto scroll-mt-16 px-4 py-24 md:px-6 lg:py-32 2xl:max-w-[1400px]">
      <div className="mx-auto max-w-2xl lg:max-w-5xl">
        <div className="text-center">
          <h1 className="text-3xl font-bold sm:text-4xl">{title}</h1>
          <p className="text-muted-foreground mt-3">{description}</p>
        </div>

        <div className="mt-12 grid items-center gap-6 lg:grid-cols-2 lg:gap-16">
          <Card className="p-0">
            <CardContent className="p-6">
              <h2 className="mb-8 text-xl font-semibold">{formTitle}</h2>
              {/* No action: submit only reveals submittedNote. */}
              <form
                noValidate
                onSubmit={(e) => {
                  e.preventDefault();
                  setSubmitted(true);
                }}
              >
                <div className="grid gap-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div>
                      <Input type="text" placeholder="First name" aria-label="First name" autoComplete="given-name" />
                    </div>
                    <div>
                      <Input type="text" placeholder="Last name" aria-label="Last name" autoComplete="family-name" />
                    </div>
                  </div>

                  <div>
                    <Input type="email" placeholder="Email" aria-label="Email" autoComplete="email" />
                  </div>

                  <div>
                    <Input type="tel" placeholder="Phone number" aria-label="Phone number" autoComplete="tel" />
                  </div>

                  <div>
                    <Textarea placeholder="Details" aria-label="Details" rows={4} />
                  </div>
                </div>

                <div className="mt-4 grid">
                  <Button type="submit">{submitLabel}</Button>
                </div>

                <div className="mt-3 text-center">
                  <p role="status" className="text-muted-foreground text-sm">
                    {submitted ? submittedNote : ''}
                  </p>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="divide-border divide-y">
            <div className="flex gap-x-7 py-6">
              <MapPin className="text-muted-foreground mt-1.5 size-6" />
              <div>
                <h3 className="font-semibold">{address.title}</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  {address.description}
                </p>
                <address className="text-muted-foreground mt-2 text-sm not-italic">
                  {address.value}
                </address>
              </div>
            </div>

            <div className="flex gap-x-7 py-6">
              <Mail className="text-muted-foreground mt-1.5 size-6" />
              <div>
                <h3 className="font-semibold">{email.title}</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  {email.description}
                </p>
                <p className="mt-2">
                  {/* email link removed (artifact rule); plain text. */}
                  <span className="text-primary text-sm font-medium">
                    {email.value}
                  </span>
                </p>
              </div>
            </div>

            <div className="flex gap-x-7 py-6">
              <Phone className="text-muted-foreground mt-1.5 size-6" />
              <div>
                <h3 className="font-semibold">{phone.title}</h3>
                <p className="text-muted-foreground mt-1 text-sm">
                  {phone.description}
                </p>
                <div className="mt-2">
                  {/* phone link removed (artifact rule); plain text. */}
                  <span className="text-primary text-sm font-medium">
                    {phone.value}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
