import type {
  CalculateShippingOptionPriceContext,
  CalculatedShippingOptionPrice,
  CreateShippingOptionDTO,
  CreateFulfillmentResult,
  FulfillmentOption,
  ValidateFulfillmentDataContext,
} from "@medusajs/framework/types";
import { AbstractFulfillmentProviderService, MedusaError } from "@medusajs/framework/utils";
import { deliveryZoneForAddress, deliveryZones } from "../../delivery-zones";

type OptionData = Record<string, unknown> & { fulfillment_type?: string };
type ShippingAddress = { city?: string | null; province?: string | null; postal_code?: string | null; address_2?: string | null };

export class StorefrontFulfillmentProvider extends AbstractFulfillmentProviderService {
  static identifier = "storefront";

  async getFulfillmentOptions(): Promise<FulfillmentOption[]> {
    return [
      { id: "delivery", name: "Delivery" },
      { id: "collection", name: "Collection" },
    ];
  }

  async validateOption(data: Record<string, unknown>): Promise<boolean> {
    return data.fulfillment_type === "delivery" || data.fulfillment_type === "collection";
  }

  async validateFulfillmentData(optionData: OptionData, data: Record<string, unknown>, context: ValidateFulfillmentDataContext): Promise<Record<string, unknown>> {
    if (optionData.fulfillment_type === "collection") return { ...data, fulfillment_type: "collection" };
    const zone = deliveryZoneForAddress(context.shipping_address as ShippingAddress);
    if (!zone) throw new MedusaError(MedusaError.Types.INVALID_DATA, "Delivery is not available for this Gauteng address");
    return { ...data, fulfillment_type: "delivery", zone_id: zone.id };
  }

  async canCalculate(option: CreateShippingOptionDTO): Promise<boolean> {
    const type = option.data?.fulfillment_type;
    return type === "collection" || (type === "delivery" && deliveryZones().length > 0);
  }

  async calculatePrice(optionData: OptionData, data: Record<string, unknown>, context: CalculateShippingOptionPriceContext): Promise<CalculatedShippingOptionPrice> {
    if (optionData.fulfillment_type === "collection") {
      return { calculated_amount: 0, is_calculated_price_tax_inclusive: true };
    }
    const address = context.shipping_address as ShippingAddress;
    const zone = deliveryZoneForAddress(address);
    if (!zone || (typeof data?.zone_id === "string" && data.zone_id !== zone.id)) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Delivery is not available for this Gauteng address");
    }
    return { calculated_amount: zone.rate_zar, is_calculated_price_tax_inclusive: true };
  }

  async createFulfillment(): Promise<CreateFulfillmentResult> { return { data: {}, labels: [] }; }
  async cancelFulfillment(): Promise<Record<string, unknown>> { return {}; }
  async createReturnFulfillment(): Promise<CreateFulfillmentResult> { return { data: {}, labels: [] }; }
}
