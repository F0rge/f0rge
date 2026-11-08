import { join } from "node:path";
import { JobLoader } from "@medusajs/framework/jobs";
import { createMedusaContainer } from "@medusajs/framework/utils";
import { asValue } from "@medusajs/framework/awilix";

class DiscoveredJobs extends JobLoader {
  readonly names: string[] = [];

  protected register(job: Parameters<JobLoader["register"]>[0]): void {
    this.names.push(job.config.name);
  }
}

test("discovered jobs retain commerce processing without the retired Firstout exception relay", async () => {
  const container = createMedusaContainer();
  container.register("logger", asValue({ debug: jest.fn(), info: jest.fn() }));
  const jobs = new DiscoveredJobs(join(__dirname, "jobs"), container);

  await jobs.load();

  expect(jobs.names).not.toContain("sync-storefront-live-exceptions");
  expect(jobs.names).toEqual(expect.arrayContaining([
    "sync-firstout-products",
    "expire-storefront-checkout-holds",
    "retry-storefront-order-handoffs",
    "process-storefront-peach-webhooks",
    "sync-storefront-fulfillment-events",
    "retry-storefront-notifications",
  ]));
});
