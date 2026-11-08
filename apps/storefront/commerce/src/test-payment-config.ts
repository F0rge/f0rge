import { MedusaError } from "@medusajs/framework/utils";
import { isHostedRuntime } from "./runtime-safety";

type Environment = Record<string, string | undefined>;

/** Test payments are opt-in and can only be registered in an explicit local/test runtime. */
export function testPaymentEnabled(env: Environment = process.env): boolean {
  if (env.STOREFRONT_TEST_PAYMENT_ENABLED !== "true") return false;
  if (isHostedRuntime(env)) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA,
      "The storefront test payment provider requires an explicit local or test runtime bound to loopback services and is disabled on hosted deployments");
  }
  return true;
}
