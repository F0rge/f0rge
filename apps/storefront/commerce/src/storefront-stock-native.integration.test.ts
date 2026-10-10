import { randomUUID } from "node:crypto";
import path from "node:path";
import { medusaIntegrationTestRunner } from "@medusajs/test-utils";
import { createOrderPaymentCollectionWorkflow } from "@medusajs/medusa/core-flows";
import type { IInventoryService, IOrderModuleService, IPaymentModuleService, IProductModuleService, IStockLocationService, MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { writeStock } from "./sync-firstout";
import { projectAvailableQuantity, type OpsProduct } from "./ops-contract";

jest.setTimeout(180_000);

const enabled = process.env.STOREFRONT_NATIVE_STOCK_LIVE_TEST === "1";
if (enabled) {
  const loopback = ["127.0.0.1", "localhost", "[::1]"];
  if (!process.env.DATABASE_URL || !process.env.REDIS_URL || !process.env.DB_HOST ||
      !loopback.includes(new URL(process.env.DATABASE_URL).hostname) ||
      !loopback.includes(new URL(process.env.REDIS_URL).hostname) || !loopback.includes(process.env.DB_HOST)) {
    throw new Error("Native stock tests require isolated local database and Redis");
  }
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("Native stock test blocks external/provider transport"); };
  const appPath = path.resolve(__dirname, "..");
  medusaIntegrationTestRunner({
    moduleName: `stock-${randomUUID().slice(0, 8)}`, cwd: appPath, medusaConfigFile: appPath,
    env: { NODE_ENV: "test", STOREFRONT_RUNTIME_KIND: "test", STOREFRONT_TEST_PAYMENT_ENABLED: "true" },
    testSuite: ({ getContainer }) => {
      describe("Ops sellable stock with real native paid reservations", () => {
        let container: MedusaContainer;
        let itemId: string;
        let variantId: string;
        let locationId: string;
        let paidReservationId: string;
        let inventory: IInventoryService;
        const sourceSkuId = randomUUID();
        const row: OpsProduct = { source_sku_id: sourceSkuId, product_group_id: null, product_title: null, options: {},
          sku: "STOCK-SOURCE", name: "Stock integrity chair", price_minor_zar: 10000, available_quantity: 5,
          revision: "2026-10-09T12:00:00Z", observed_at: "2026-10-09T12:00:00Z", acknowledged_commitment_ids: [], made_to_order_offer: null };
        const pending = [{ commitment_id: "storefront:paid:line", source_sku_id: sourceSkuId, quantity: 1 }];
        const available = async () => Number(await inventory.retrieveAvailableQuantity(itemId, [locationId]));
        beforeAll(async () => {
          container = getContainer();
          inventory = container.resolve(Modules.INVENTORY);
          const locations = container.resolve<IStockLocationService>(Modules.STOCK_LOCATION);
          const location = await locations.createStockLocations({ name: "Stock integrity fixture" });
          locationId = location.id;
          const products = container.resolve<IProductModuleService>(Modules.PRODUCT);
          const product = await products.createProducts({ title: "Stock integrity chair", options: [{ title: "Item", values: ["Standard"] }],
            variants: [{ title: "Standard", sku: `STOCK-${randomUUID()}`, manage_inventory: true, options: { Item: "Standard" } }] });
          variantId = product.variants![0].id;
          const item = await inventory.createInventoryItems({ sku: `INV-${randomUUID()}` });
          itemId = item.id;
          const link = container.resolve(ContainerRegistrationKeys.LINK);
          await link.create({ [Modules.PRODUCT]: { variant_id: variantId }, [Modules.INVENTORY]: { inventory_item_id: itemId } });
          await inventory.createInventoryLevels({ inventory_item_id: itemId, location_id: locationId, stocked_quantity: 5 });
          const orders = container.resolve<IOrderModuleService>(Modules.ORDER);
          const order = await orders.createOrders({ currency_code: "zar", email: "stock@example.test", status: "completed",
            metadata: { storefront_confirmation_sha256: "a".repeat(64) },
            items: [{ title: "Stock integrity chair", quantity: 1, unit_price: 100, variant_id: variantId }] });
          const { result: collections } = await createOrderPaymentCollectionWorkflow(container).run({ input: { order_id: order.id, amount: 100 } });
          const payments = container.resolve<IPaymentModuleService>(Modules.PAYMENT);
          const session = await payments.createPaymentSession(collections[0].id, { provider_id: "pp_storefront-test_local", currency_code: "zar", amount: 100, data: {} });
          const payment = await payments.authorizePaymentSession(session.id, {});
          if (!payment) throw new Error("Fixture payment authorization failed");
          await payments.capturePayment({ payment_id: payment.id });
          const reservation = await inventory.createReservationItems({ line_item_id: order.items![0].id, inventory_item_id: itemId, location_id: locationId, quantity: 1 });
          paidReservationId = reservation.id;
        });
        afterAll(() => { globalThis.fetch = originalFetch; });
        test("counts a paid commitment exactly once before and after Ops acknowledgement, while preserving live cart holds", async () => {
          expect(await available()).toBe(4);
          await writeStock(container, variantId, locationId, projectAvailableQuantity(row, pending));
          expect(await available()).toBe(4);
          const acknowledged = { ...row, available_quantity: 4, acknowledged_commitment_ids: [pending[0].commitment_id] };
          await writeStock(container, variantId, locationId, projectAvailableQuantity(acknowledged, pending));
          expect(await available()).toBe(4);
          const hold = await inventory.createReservationItems({ inventory_item_id: itemId, location_id: locationId, quantity: 1, created_by: "storefront_hold:another_cart" });
          await writeStock(container, variantId, locationId, 4);
          expect(await available()).toBe(3);
          await inventory.deleteReservationItems(hold.id);
          expect(await available()).toBe(4);
          // Native fulfillment consumes the original order reservation and one
          // stocked unit. A later Ops projection must retain four sellable units.
          await inventory.deleteReservationItems(paidReservationId);
          await inventory.adjustInventory(itemId, locationId, -1);
          await writeStock(container, variantId, locationId, 4);
          expect(await available()).toBe(4);
          await writeStock(container, variantId, locationId, 4);
          expect(await available()).toBe(4);
        });
      });
    },
  });
} else {
  describe.skip("native stock integration requires explicit isolated local services", () => {
    test("opt in with STOREFRONT_NATIVE_STOCK_LIVE_TEST=1", () => undefined);
  });
}
