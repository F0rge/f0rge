import { MedusaError } from "@medusajs/framework/utils";

type Environment = Record<string, string | undefined>;

/** Test payments are opt-in and can only be registered in an explicit local/test runtime. */
export function testPaymentEnabled(env: Environment = process.env): boolean {
  if (env.STOREFRONT_TEST_PAYMENT_ENABLED !== "true") return false;
  const hostedRuntime = [
    "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID", "VERCEL", "VERCEL_ENV",
    "FLY_APP_NAME", "RENDER", "K_SERVICE",
  ].some((name) => !!env[name]);
  const explicitLocalRuntime = env.STOREFRONT_RUNTIME_KIND === "local" && env.NODE_ENV === "development";
  const explicitTestRuntime = env.STOREFRONT_RUNTIME_KIND === "test" && env.NODE_ENV === "test";
  if (env.NODE_ENV === "production" || hostedRuntime || !(explicitLocalRuntime || explicitTestRuntime)) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA,
      "The storefront test payment provider requires an explicit local or test runtime and is disabled on hosted deployments");
  }
  return true;
}
