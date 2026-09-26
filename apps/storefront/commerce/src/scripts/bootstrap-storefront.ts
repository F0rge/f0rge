import type { ExecArgs } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import {
  createApiKeysWorkflow,
  createRegionsWorkflow,
  createSalesChannelsWorkflow,
  createStockLocationsWorkflow,
  createStoresWorkflow,
  createTaxRegionsWorkflow,
  linkSalesChannelsToApiKeyWorkflow,
  linkSalesChannelsToStockLocationWorkflow,
  updateRegionsWorkflow,
  updateStoresWorkflow,
} from "@medusajs/medusa/core-flows";

// Adapted from Medusa DTC starter e3a237c initial-data-seed.ts; no demo apparel.
export default async function bootstrapStorefront({ container }: ExecArgs) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);

  const { data: salesChannels } = await query.graph({
    entity: "sales_channel", fields: ["id", "name"],
  });
  let channelId = salesChannels[0]?.id;
  if (!channelId) {
    const { result } = await createSalesChannelsWorkflow(container).run({
      input: { salesChannelsData: [{ name: "Storefront", description: "Firstout retail website" }] },
    });
    channelId = result[0].id;
  }

  const { data: stores } = await query.graph({ entity: "store", fields: ["id", "supported_currencies.*"] });
  if (!stores.length) {
    await createStoresWorkflow(container).run({
      input: { stores: [{
        name: "Storefront",
        supported_currencies: [{ currency_code: "zar", is_default: true, is_tax_inclusive: true }],
        default_sales_channel_id: channelId,
      }] },
    });
  }
  for (const store of stores) {
    const currencies = (store.supported_currencies || []).filter((currency) => currency !== null);
    if (currencies.length > 1) {
      throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE,
        "Store has multiple currencies; set ZAR tax-inclusive in Medusa Admin before syncing Firstout");
    }
    // Medusa creates a new store with EUR as its only currency. This dedicated
    // Storefront uses ZAR exclusively, so normalize that default on first boot.
    await updateStoresWorkflow(container).run({ input: {
      selector: { id: store.id },
      update: { supported_currencies: [{ currency_code: "zar", is_default: true, is_tax_inclusive: true }] },
    } });
  }

  const { data: keys } = await query.graph({
    entity: "api_key", fields: ["id", "type"], filters: { type: "publishable" },
  });
  if (!keys.length) {
    const { result: [key] } = await createApiKeysWorkflow(container).run({
      input: { api_keys: [{ title: "Storefront public key", type: "publishable", created_by: "" }] },
    });
    await linkSalesChannelsToApiKeyWorkflow(container).run({
      input: { id: key.id, add: [channelId] },
    });
  }

  const { data: regions } = await query.graph({
    entity: "region", fields: ["id", "currency_code"],
  });
  if (!regions.some((region) => region.currency_code === "zar")) {
    await createRegionsWorkflow(container).run({
      input: { regions: [{
        name: "South Africa", currency_code: "zar", countries: ["za"], is_tax_inclusive: true,
        payment_providers: ["pp_system_default"],
      }] },
    });
    await createTaxRegionsWorkflow(container).run({
      input: [{ country_code: "za", provider_id: "tp_system" }],
    });
  }
  for (const region of regions) {
    if (region.currency_code === "zar") {
      await updateRegionsWorkflow(container).run({ input: {
        selector: { id: region.id }, update: { is_tax_inclusive: true },
      } });
    }
  }

  const { data: locations } = await query.graph({
    entity: "stock_location", fields: ["id", "name"],
  });
  if (!locations.length) {
    const { result: [location] } = await createStockLocationsWorkflow(container).run({
      input: { locations: [{
        name: "Firstout online stock",
        address: { city: "Johannesburg", country_code: "ZA", address_1: "" },
      }] },
    });
    await linkSalesChannelsToStockLocationWorkflow(container).run({
      input: { id: location.id, add: [channelId] },
    });
    const link = container.resolve(ContainerRegistrationKeys.LINK);
    await link.create({
      [Modules.STOCK_LOCATION]: { stock_location_id: location.id },
      [Modules.FULFILLMENT]: { fulfillment_provider_id: "manual_manual" },
    });
  }

  logger.info("South African Storefront bootstrap complete. Set the public API key from Medusa Admin.");
}
