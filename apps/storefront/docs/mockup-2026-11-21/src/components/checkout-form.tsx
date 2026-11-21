// Original (shadcn/ui): no free checkout-form block exists. Built from the installed
// Card, Input, Label, Textarea and Button. radio-group is not installed, so the
// delivery/collection choice uses native radios (accent-primary, size-4).
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { checkout } from '@/content';

// 16px text at every width (the stock Input/Textarea drop to 14px from md).
const field = 'md:text-base';

export function CheckoutForm() {
  const [method, setMethod] = useState(checkout.methods[0].id);
  const [submitted, setSubmitted] = useState(false);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">{checkout.title}</CardTitle>
        <CardDescription>{checkout.guestNote}</CardDescription>
      </CardHeader>
      <CardContent>
        {/* ponytail: no action, noValidate — nothing is sent; submit only reveals the note. */}
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
          }}
          className="grid gap-8"
        >
          <fieldset className="grid gap-4">
            <legend className="mb-4 font-medium">Contact</legend>
            <div className="grid gap-2">
              <Label htmlFor="co-email">Email</Label>
              <Input id="co-email" type="email" autoComplete="email" className={field} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="co-phone">Phone</Label>
              <Input id="co-phone" type="tel" autoComplete="tel" className={field} />
            </div>
          </fieldset>

          <fieldset className="grid gap-3">
            <legend className="mb-4 font-medium">Delivery or collection</legend>
            {checkout.methods.map((m) => (
              <label
                key={m.id}
                htmlFor={`co-method-${m.id}`}
                className="has-[:checked]:border-primary flex cursor-pointer items-start gap-3 rounded-md border p-4"
              >
                <input
                  id={`co-method-${m.id}`}
                  type="radio"
                  name="method"
                  value={m.id}
                  checked={method === m.id}
                  onChange={() => setMethod(m.id)}
                  className="accent-primary mt-0.5 size-4 shrink-0"
                />
                <span className="grid gap-1">
                  <span className="text-sm leading-none font-medium">{m.label}</span>
                  <span className="text-muted-foreground text-sm">{m.description}</span>
                </span>
              </label>
            ))}
          </fieldset>

          {method === 'delivery' && (
            <fieldset className="grid gap-4">
              <legend className="mb-4 font-medium">Delivery address</legend>
              <div className="grid gap-2">
                <Label htmlFor="co-street">Street address</Label>
                <Input id="co-street" autoComplete="street-address" className={field} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="co-suburb">Suburb or area</Label>
                <Input
                  id="co-suburb"
                  autoComplete="address-level3"
                  aria-describedby="co-suburb-note"
                  className={field}
                />
                <p id="co-suburb-note" className="text-muted-foreground text-sm">
                  We deliver in selected Gauteng areas.
                </p>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="co-city">City</Label>
                  <Input id="co-city" autoComplete="address-level2" className={field} />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="co-postal">Postal code</Label>
                  <Input
                    id="co-postal"
                    inputMode="numeric"
                    autoComplete="postal-code"
                    className={field}
                  />
                </div>
              </div>
            </fieldset>
          )}

          <div className="grid gap-2">
            <Label htmlFor="co-note">Order note (optional)</Label>
            <Textarea id="co-note" rows={3} className={field} />
          </div>

          <div className="grid gap-3">
            <Button type="submit" size="lg" className="w-full">
              Place order
            </Button>
            <p role="status" className="text-muted-foreground text-center text-sm">
              {submitted ? checkout.notPlaced : ''}
            </p>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
