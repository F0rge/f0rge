import ShippingReturnsSplitColumns from '@/components/blocks/ecommerce/ecommerce-shipping-returns/split-columns';
import ShippingReturnsAccordion from '@/components/blocks/ecommerce/ecommerce-shipping-returns/accordion';
import SplitWithDetails from '@/components/blocks/marketing/contact-sections/split-with-details';
import { Block } from '@/components/block';
import { contactCopy, hoursLine, policy, showroom } from '@/content';
import { Ban, Clock, PackageX, Receipt, RefreshCw, Store, Truck, Wrench } from 'lucide-react';

/** #help (alias #delivery): delivery and collection, returns, contact. */
export default function HelpPage() {
  return (
    <>
      <Block name="ecommerce-shipping-returns/split-columns" collection="ecommerce">
        <ShippingReturnsSplitColumns
          columns={[
            {
              title: 'Delivery and collection',
              items: [
                { icon: Truck, title: 'Delivery', description: policy.delivery },
                { icon: Receipt, title: 'Delivery charges', description: policy.deliveryCharges },
                { icon: Store, title: 'Collection', description: `Collect from our showroom at ${showroom.address}.` },
                { icon: Clock, title: 'Showroom hours', description: `${hoursLine}.` },
              ],
            },
            {
              title: 'Returns',
              items: [
                { icon: RefreshCw, title: 'Change of mind', description: policy.changeOfMind },
                { icon: Ban, title: 'Not returnable for a change of mind', description: `${policy.notReturnable}` },
                { icon: PackageX, title: 'Wrong or not as described', description: policy.wrongItem },
                { icon: Wrench, title: 'Faulty', description: policy.faulty },
              ],
            },
          ]}
        />
      </Block>

      <div id="returns" className="scroll-mt-16">
        <Block name="ecommerce-shipping-returns/accordion" collection="ecommerce">
          <ShippingReturnsAccordion
            title="Help"
            description="Delivery, collection and returns, in detail."
            delivery={{
              title: 'Delivery and collection',
              subtitle: 'Selected Gauteng areas, or collect',
              columns: [
                {
                  title: 'Delivery',
                  points: [
                    'Selected Gauteng areas',
                    'Charges shown in rand, including VAT',
                    'Confirmed in your order total before payment',
                  ],
                },
                {
                  title: 'Collection',
                  points: [showroom.short, ...showroom.hours.map((h) => `${h.days}: ${h.time}`)],
                },
              ],
              note: 'Choose delivery or collection at checkout.',
            }}
            timing={{
              title: 'Faulty furniture',
              subtitle: 'Claims within 12 months of purchase',
              steps: [
                { title: 'Tell us', description: 'Contact us with your order number and what is wrong.' },
                {
                  title: 'Assessment',
                  description: 'We may quote an assessment fee first. It is refunded if the fault is confirmed.',
                },
                { title: 'Your choice', description: 'Repair, replacement or refund.' },
              ],
              callout: { title: 'Natural markings', description: policy.markings },
            }}
            returns={{
              title: 'Returns',
              subtitle: 'Change of mind within 30 days',
              returnable: {
                title: 'Can be returned',
                points: [
                  'Within 30 days of delivery or collection',
                  'Unused, in the original condition and packaging, tags on',
                  'With the invoice or delivery note',
                ],
              },
              nonReturnable: {
                title: 'Cannot be returned for a change of mind',
                points: [
                  'Bespoke or personalised pieces',
                  'Pieces made to a measurement, fabric or finish chosen for your order',
                ],
              },
              processTitle: 'How to return',
              steps: [
                { title: 'Contact us', description: 'With your order number, before sending anything back.' },
                { title: 'Agree collection or drop-off', description: policy.collectionFee },
                { title: 'Refund', description: 'The original delivery charge is not refunded on a change of mind.' },
              ],
              callout: { title: 'Wrong or not as described?', description: policy.wrongItem },
            }}
          />
        </Block>
      </div>

      <Block name="contact-sections/split-with-details" collection="marketing">
        <SplitWithDetails
          id="contact"
          title="Contact us"
          description="Questions about a piece, delivery, collection or an order."
          formTitle="Send us a message"
          submitLabel="Send message"
          submittedNote={contactCopy.notSent}
          address={{ title: 'Showroom', description: `${hoursLine}.`, value: showroom.address }}
          email={{ title: 'Email', description: 'For questions about a piece or an order.', value: showroom.email }}
          phone={{
            title: 'Phone',
            description: 'Mobile and showroom.',
            value: showroom.phones.map((p) => (
              <span key={p.number} className="block">
                {p.label}: {p.number}
              </span>
            )),
          }}
        />
      </Block>
    </>
  );
}
