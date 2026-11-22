import { ContainerRegistrationKeys, MedusaError } from "@medusajs/framework/utils";
import PaymentModule from "@medusajs/medusa/payment";
import medusaPackage from "@medusajs/medusa/package.json";
import type { Knex } from "knex";
import { withStorefrontRefundWriter } from "./refund-cutover";

const legacyRefundGate = Symbol.for("f0rge.daskasas.legacy-refund-gate");

export function installLegacyMedusaRefundGate(): void {
  if (medusaPackage.version !== "2.21.1") {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The legacy storefront refund gate requires Medusa 2.21.1");
  }

  const NativePaymentService = PaymentModule.service;
  const marker = Object.getOwnPropertyDescriptor(NativePaymentService, legacyRefundGate);
  const nativeRefund = NativePaymentService.prototype.refundPayment;
  if (typeof nativeRefund !== "function" || (marker && marker.value !== nativeRefund)) {
    throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The native Medusa refund method has changed");
  }
  if (marker) return;

  type PaymentServiceArguments = ConstructorParameters<typeof NativePaymentService>;
  type RefundArguments = Parameters<InstanceType<typeof NativePaymentService>["refundPayment"]>;
  type PaymentDependencies = PaymentServiceArguments[0] & {
    [ContainerRegistrationKeys.PG_CONNECTION]?: Knex;
  };

  class GatedPaymentService extends NativePaymentService {
    private readonly paymentDependencies: PaymentDependencies;

    constructor(...args: PaymentServiceArguments) {
      super(...args);
      this.paymentDependencies = args[0];
    }

    override async refundPayment(...args: RefundArguments) {
      const db = this.paymentDependencies[ContainerRegistrationKeys.PG_CONNECTION];
      if (!db) {
        throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "The storefront refund gate requires the shared PostgreSQL connection");
      }
      return withStorefrontRefundWriter(db, { operation: "native_refund", referenceId: args[0].payment_id },
        () => super.refundPayment(...args));
    }
  }

  // The 2.21.1 loader follows the package's discovery path for models and
  // migrations. Replace only the service in that same module object.
  Object.defineProperty(GatedPaymentService, legacyRefundGate, {
    value: GatedPaymentService.prototype.refundPayment,
  });
  PaymentModule.service = GatedPaymentService;
}
