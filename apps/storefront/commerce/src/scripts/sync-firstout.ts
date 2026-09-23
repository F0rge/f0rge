import type { ExecArgs } from "@medusajs/framework/types";
import { syncFirstout } from "../sync-firstout";

export default async function syncFirstoutScript({ container }: ExecArgs) {
  await syncFirstout(container);
}
