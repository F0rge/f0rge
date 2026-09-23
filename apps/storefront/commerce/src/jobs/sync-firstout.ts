import type { MedusaContainer } from "@medusajs/framework/types";
import { syncFirstout } from "../sync-firstout";

export default async function syncFirstoutJob(container: MedusaContainer) {
  await syncFirstout(container);
}

export const config = {
  name: "sync-firstout-products",
  schedule: "* * * * *",
};
