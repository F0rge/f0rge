import { removeShippingMethodFromCartStep } from "@medusajs/medusa/core-flows";
import { createWorkflow } from "@medusajs/framework/workflows-sdk";

type ClearCheckoutShippingInput = { shipping_method_ids: string[] };

export const clearCheckoutShippingWorkflow = createWorkflow(
  "clear-checkout-shipping",
  (input: ClearCheckoutShippingInput) => {
    removeShippingMethodFromCartStep(input);
  },
);
