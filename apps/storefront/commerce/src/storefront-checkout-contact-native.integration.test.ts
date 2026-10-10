import { randomUUID } from "node:crypto";
import path from "node:path";
import { medusaIntegrationTestRunner } from "@medusajs/test-utils";
import type { ICartModuleService, ICustomerModuleService, ILockingModule, ISalesChannelModuleService, MedusaContainer } from "@medusajs/framework/types";
import { Modules } from "@medusajs/framework/utils";
import { updateStorefrontCheckoutContact } from "./storefront-checkout-contact";

jest.setTimeout(180_000);
const enabled = process.env.STOREFRONT_NATIVE_CONTACT_LIVE_TEST === "1";
if (enabled) {
  const loopback = ["localhost", "127.0.0.1", "[::1]"];
  if (!process.env.DATABASE_URL || !process.env.REDIS_URL || !process.env.DB_HOST ||
      !loopback.includes(new URL(process.env.DATABASE_URL).hostname) ||
      !loopback.includes(new URL(process.env.REDIS_URL).hostname) || !loopback.includes(process.env.DB_HOST)) {
    throw new Error("Native contact tests require isolated local database and Redis");
  }
  const appPath = path.resolve(__dirname, "..");
  medusaIntegrationTestRunner({ moduleName: `contact-${randomUUID().slice(0, 8)}`, cwd: appPath, medusaConfigFile: appPath,
    env: { NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test", STOREFRONT_TEST_PAYMENT_ENABLED: "true" },
    testSuite: ({ getContainer }) => {
      test("guest contact never becomes account ownership, even for a registered email, and signed-in ownership survives different contact email", async () => {
        const container: MedusaContainer = getContainer();
        const carts = container.resolve<ICartModuleService>(Modules.CART);
        const customers = container.resolve<ICustomerModuleService>(Modules.CUSTOMER);
        const channels = container.resolve<ISalesChannelModuleService>(Modules.SALES_CHANNEL);
        const channel = await channels.createSalesChannels({ name: "Contact security fixture" });
        const owner = await customers.createCustomers({ email: `registered-${randomUUID()}@example.test`, has_account: true });
        for (const email of [`guest-${randomUUID()}@example.test`, owner.email!]) {
          const cart = await carts.createCarts({ currency_code: "zar", sales_channel_id: channel.id });
          await updateStorefrontCheckoutContact(container, { id: cart.id, email, customer_id: null });
          const stored = await carts.retrieveCart(cart.id);
          expect(stored.email).toBe(email);
          expect(stored.customer_id).toBeNull();
        }
        const accountCart = await carts.createCarts({ currency_code: "zar", sales_channel_id: channel.id, customer_id: owner.id });
        const contactEmail = `different-contact-${randomUUID()}@example.test`;
        await updateStorefrontCheckoutContact(container, { id: accountCart.id, email: contactEmail, customer_id: owner.id });
        const stored = await carts.retrieveCart(accountCart.id);
        expect(stored.customer_id).toBe(owner.id);
        expect(stored.email).toBe(contactEmail);
      });
      test("a concurrent verified ownership attachment prevents checkout from writing its stale guest owner", async () => {
        const container: MedusaContainer = getContainer();
        const carts = container.resolve<ICartModuleService>(Modules.CART);
        const customers = container.resolve<ICustomerModuleService>(Modules.CUSTOMER);
        const locking = container.resolve<ILockingModule>(Modules.LOCKING);
        const owner = await customers.createCustomers({ email: `race-owner-${randomUUID()}@example.test`, has_account: true });
        const cart = await carts.createCarts({ currency_code: "zar" });
        let signalAttachmentStarted: () => void = () => undefined;
        const attachmentStarted = new Promise<void>((resolve) => { signalAttachmentStarted = resolve; });
        let releaseAttachment: () => void = () => undefined;
        const attachmentGate = new Promise<void>((resolve) => { releaseAttachment = resolve; });
        const attachment = locking.execute(`storefront-cart-owner:${cart.id}`, async () => {
          signalAttachmentStarted();
          await attachmentGate;
          await carts.updateCarts(cart.id, { customer_id: owner.id });
        }, { timeout: 5, expire: 15 });
        await attachmentStarted;
        // Checkout read null before the verified attachment started. Its contact
        // update must wait for the shared lock and reject that stale ownership.
        const contact = updateStorefrontCheckoutContact(container, {
          id: cart.id, email: "race-guest@example.test", customer_id: null,
        }).then(() => ({ rejected: false, type: undefined }), (error: unknown) => ({
          rejected: true, type: error instanceof Error && "type" in error ? error.type : undefined,
        }));
        releaseAttachment();
        await attachment;
        expect(await contact).toEqual({ rejected: true, type: "conflict" });
        expect((await carts.retrieveCart(cart.id)).customer_id).toBe(owner.id);
      });
    },
  });
} else {
  describe.skip("native checkout contact integration requires explicit isolated local services", () => {
    test("opt in with STOREFRONT_NATIVE_CONTACT_LIVE_TEST=1", () => undefined);
  });
}
