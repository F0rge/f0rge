import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ArrowRight, Clock, Mail, MapPin, Phone } from 'lucide-react';

export interface QuickContactCTAProps {
  /** Root id, for #home/visit links. */
  id?: string;
  title: string;
  description: string;
  address: { title: string; description: string; value: string };
  hours: { title: string; rows: { days: string; time: string }[] };
  phones: { title: string; numbers: { label: string; number: string }[] };
  email: { title: string; description: string; value: string };
  form: {
    title: string;
    subjects: string[];
    submitLabel: string;
    /** Shown after submit; nothing is sent. */
    submittedNote: string;
  };
}

// The demo's Live Chat and Book a Demo rows, the "within 24 hours" promise and the privacy
// line are dropped; mailto:/tel: links are plain text (artifact rule). The four rows are the
// showroom's address, hours, phones and email.
export default function QuickContactCTA({
  id,
  title,
  description,
  address,
  hours,
  phones,
  email,
  form,
}: QuickContactCTAProps) {
  const [submitted, setSubmitted] = useState(false);
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <>
      {/* Quick Contact CTA Section */}
      <div id={id} className="scroll-mt-16 py-16 md:py-24">
        <div className="container mx-auto px-4 md:px-6 2xl:max-w-[1400px]">
          <div className="overflow-hidden rounded-xl border">
            <div className="grid md:grid-cols-2">
              <div className="bg-primary text-primary-foreground p-8 md:p-12">
                <div className="space-y-4">
                  <h2 className="text-3xl font-bold tracking-tighter md:text-4xl">
                    {title}
                  </h2>
                  <p className="md:text-lg">{description}</p>
                </div>
                <div className="mt-8 space-y-6">
                  <div className="flex items-start gap-3">
                    <MapPin className="mt-0.5 h-6 w-6 shrink-0" />
                    <div>
                      <h3 className="mb-1 font-medium">{address.title}</h3>
                      <p className="text-primary-foreground/80 text-sm">
                        {address.description}
                      </p>
                      <address className="mt-1 inline-flex text-sm font-medium not-italic">
                        {address.value}
                      </address>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Clock className="mt-0.5 h-6 w-6 shrink-0" />
                    <div>
                      <h3 className="mb-1 font-medium">{hours.title}</h3>
                      <table className="mt-1 text-sm">
                        <tbody>
                          {hours.rows.map((row) => (
                            <tr key={row.days}>
                              <th
                                scope="row"
                                className="text-primary-foreground/80 py-0.5 pr-6 text-left font-normal"
                              >
                                {row.days}
                              </th>
                              <td className="py-0.5 font-medium tabular-nums">{row.time}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Phone className="mt-0.5 h-6 w-6 shrink-0" />
                    <div>
                      <h3 className="mb-1 font-medium">{phones.title}</h3>
                      {phones.numbers.map((p) => (
                        <p key={p.number} className="text-sm">
                          <span className="text-primary-foreground/80">{p.label}: </span>
                          <span className="font-medium">{p.number}</span>
                        </p>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <Mail className="mt-0.5 h-6 w-6 shrink-0" />
                    <div>
                      <h3 className="mb-1 font-medium">{email.title}</h3>
                      <p className="text-primary-foreground/80 text-sm">
                        {email.description}
                      </p>
                      <span className="mt-1 inline-flex text-sm font-medium">
                        {email.value}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-card p-8 md:p-12">
                <form onSubmit={handleSubmit} noValidate className="space-y-4">
                  <div className="space-y-2">
                    <h3 className="text-xl font-bold">{form.title}</h3>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="visit-name">Name</Label>
                      <Input id="visit-name" placeholder="Your name" autoComplete="name" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="visit-email">Email</Label>
                      <Input
                        id="visit-email"
                        type="email"
                        placeholder="Your email"
                        autoComplete="email"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="visit-subject">Subject</Label>
                    <Select>
                      <SelectTrigger id="visit-subject">
                        <SelectValue placeholder="Select a subject" />
                      </SelectTrigger>
                      <SelectContent>
                        {form.subjects.map((subject) => (
                          <SelectItem key={subject} value={subject}>
                            {subject}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="visit-message">Message</Label>
                    <Textarea
                      id="visit-message"
                      placeholder="How can we help you?"
                      rows={4}
                    />
                  </div>
                  <Button type="submit" size="lg" className="w-full">
                    {form.submitLabel}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                  <p role="status" className="text-muted-foreground text-center text-xs">
                    {submitted ? form.submittedNote : ''}
                  </p>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* End Quick Contact CTA Section */}
    </>
  );
}
