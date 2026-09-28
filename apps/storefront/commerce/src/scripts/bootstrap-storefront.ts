import type { ExecArgs } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import {
  createApiKeysWorkflow,
  createLocationFulfillmentSetWorkflow,
  createRegionsWorkflow,
  createSalesChannelsWorkflow,
  createServiceZonesWorkflow,
  createShippingOptionsWorkflow,
  createStockLocationsWorkflow,
  createStoresWorkflow,
  createTaxRatesWorkflow,
  createTaxRegionsWorkflow,
  updateTaxRatesWorkflow,
  linkSalesChannelsToApiKeyWorkflow,
  linkSalesChannelsToStockLocationWorkflow,
  updateRegionsWorkflow,
  updateStoresWorkflow,
} from "@medusajs/medusa/core-flows";
import { deliveryZones } from "../delivery-zones";
import { testPaymentEnabled } from "../test-payment-config";
import { southAfricaVatRate } from "../vat-config";

// Adapted from Medusa DTC starter e3a237c initial-data-seed.ts; no demo apparel.
export default async function bootstrapStorefront({ container }: ExecArgs) {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const logger = container.resolve(ContainerRegistrationKeys.LOGGER);
  const enableTestPayment = testPaymentEnabled();

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
        name: "South Africa", currency_code: "zar", countries: ["za"], is_tax_inclusive: true, automatic_taxes: true,
        payment_providers: ["pp_system_default", ...(enableTestPayment ? ["pp_storefront-test_local"] : [])],
      }] },
    });
    await createTaxRegionsWorkflow(container).run({
      input: [{ country_code: "za", provider_id: "tp_system" }],
    });
  }
  for (const region of regions) {
    if (region.currency_code === "zar") {
      await updateRegionsWorkflow(container).run({ input: {
        selector: { id: region.id }, update: {
          is_tax_inclusive: true,
          automatic_taxes: true,
          payment_providers: ["pp_system_default", ...(enableTestPayment ? ["pp_storefront-test_local"] : [])],
        },
      } });
    }
  }

  const { data: taxRegions } = await query.graph({
    entity: "tax_region", fields: ["id", "country_code", "province_code"], filters: { country_code: "za" },
  });
  let taxRegionId = taxRegions.find((candidate) => !candidate.province_code)?.id;
  if (!taxRegionId) {
    const { result: [createdTaxRegion] } = await createTaxRegionsWorkflow(container).run({ input: [{ country_code: "za", provider_id: "tp_system" }] });
    taxRegionId = createdTaxRegion.id;
  }
  const vatRate = southAfricaVatRate();
  const { data: taxRates } = await query.graph({
    entity: "tax_rate", fields: ["id", "rate", "is_default", "tax_region_id"], filters: { tax_region_id: taxRegionId },
  });
  const defaultRate = taxRates.find((candidate) => candidate.is_default);
  if (defaultRate) {
    if (Number(defaultRate.rate) !== vatRate) {
      await updateTaxRatesWorkflow(container).run({ input: {
        selector: { id: defaultRate.id }, update: { rate: vatRate, name: "South Africa VAT", code: "VAT", is_default: true },
      } });
    }
  } else {
    await createTaxRatesWorkflow(container).run({ input: [{
      tax_region_id: taxRegionId, name: "South Africa VAT", code: "VAT", rate: vatRate, is_default: true,
    }] });
  }

  const { data: locations } = await query.graph({
    entity: "stock_location", fields: ["id", "name", "fulfillment_sets.id", "fulfillment_sets.name", "fulfillment_sets.type", "fulfillment_sets.service_zones.id", "fulfillment_sets.service_zones.name"],
  });
  let locationId = locations[0]?.id;
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
    locationId = location.id;
  }

  if (!locationId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Store stock location is missing");
  const { data: locationsWithProviders } = await query.graph({
    entity: "stock_location", fields: ["id", "fulfillment_providers.id"], filters: { id: locationId },
  });
  const providerIds = ((locationsWithProviders[0] as { fulfillment_providers?: ({ id: string } | null)[] } | undefined)
    ?.fulfillment_providers || []).filter(Boolean).map((provider) => provider!.id);
  if (!providerIds.includes("storefront_storefront")) {
    const link = container.resolve(ContainerRegistrationKeys.LINK);
    await link.create({
      [Modules.STOCK_LOCATION]: { stock_location_id: locationId },
      [Modules.FULFILLMENT]: { fulfillment_provider_id: "storefront_storefront" },
    });
  }
  type BootstrapServiceZone = { id: string; name: string };
  type BootstrapFulfillmentSet = { id: string; name: string; type: string; service_zones?: (BootstrapServiceZone | null)[] };
  const locationFulfillmentSets = (locations[0]?.fulfillment_sets || []).filter(Boolean) as BootstrapFulfillmentSet[];
  let shippingSet: BootstrapFulfillmentSet | undefined = locationFulfillmentSets.find((set) => set.type === "shipping");
  if (!shippingSet) {
    await createLocationFulfillmentSetWorkflow(container).run({ input: {
      location_id: locationId,
      fulfillment_set_data: { name: "Storefront shipping", type: "shipping" },
    } });
    const { data: refreshed } = await query.graph({
      entity: "stock_location", fields: ["id", "fulfillment_sets.id", "fulfillment_sets.name", "fulfillment_sets.type", "fulfillment_sets.service_zones.id", "fulfillment_sets.service_zones.name"],
      filters: { id: locationId },
    });
    shippingSet = ((refreshed[0]?.fulfillment_sets || []).filter(Boolean) as BootstrapFulfillmentSet[])
      .find((set) => set.type === "shipping");
  }
  if (!shippingSet) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Store shipping set could not be created");

  let serviceZone: BootstrapServiceZone | undefined = shippingSet.service_zones?.find((zone) => zone?.name === "South Africa") || undefined;
  if (!serviceZone) {
    const { result: [createdZone] } = await createServiceZonesWorkflow(container).run({ input: { data: [{
      name: "South Africa", fulfillment_set_id: shippingSet.id,
      geo_zones: [{ type: "country", country_code: "za" }],
    }] } });
    serviceZone = { id: createdZone.id, name: createdZone.name };
  }

  const { data: profiles } = await query.graph({ entity: "shipping_profile", fields: ["id", "name", "type"] });
  const shippingProfile = profiles[0];
  if (!shippingProfile) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "A shipping profile is required for checkout");
  const { data: options } = await query.graph({
    entity: "shipping_option", fields: ["id", "name", "service_zone.id"],
  });
  const existingNames = new Set(options
    .filter((option: { service_zone?: { id?: string } }) => option.service_zone?.id === serviceZone.id)
    .map((option: { name: string }) => option.name));
  const configuredOptions = [
    { name: "Collection", code: "collection", description: "Collect from the configured collection point", fulfillment_type: "collection" },
    ...(deliveryZones().length ? [{ name: "Gauteng delivery", code: "delivery", description: "Server-rated Gauteng delivery", fulfillment_type: "delivery" }] : []),
  ];
  const newOptions = configuredOptions.filter(({ name }) => !existingNames.has(name)).map((option) => ({
    name: option.name,
    service_zone_id: serviceZone.id,
    shipping_profile_id: shippingProfile.id,
    provider_id: "storefront_storefront",
    type: { label: option.name, description: option.description, code: option.code },
    price_type: "calculated" as const,
    data: { fulfillment_type: option.fulfillment_type },
  }));
  if (newOptions.length) await createShippingOptionsWorkflow(container).run({ input: newOptions });

  logger.info("South African Storefront bootstrap complete. Set the public API key from Medusa Admin.");
}
