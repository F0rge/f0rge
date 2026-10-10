import { loadEnv, defineConfig } from '@medusajs/framework/utils'
import { assertHostedCommerceConfig } from './src/hosted-commerce-config'
import { hostedLocalFileOptions } from './src/file-storage-url'
import { testPaymentEnabled } from './src/test-payment-config'
import { peachPaymentEnabled } from './src/peach-payment-config'

loadEnv(process.env.NODE_ENV || 'development', process.cwd())
assertHostedCommerceConfig(process.env)

const modules: Record<string, unknown>[] = process.env.REDIS_URL ? [
  {
    resolve: "@medusajs/medusa/event-bus-redis",
    options: { redisUrl: process.env.REDIS_URL },
  },
  {
    resolve: "@medusajs/medusa/workflow-engine-redis",
    options: { redis: { redisUrl: process.env.REDIS_URL } },
  },
  {
    resolve: "@medusajs/medusa/locking",
    options: { providers: [{
      resolve: "@medusajs/medusa/locking-redis",
      id: "locking-redis",
      is_default: true,
      options: { redisUrl: process.env.REDIS_URL },
    }] },
  },
] : []

const notificationProviders: Record<string, unknown>[] = []
if (process.env.STOREFRONT_SENDGRID_API_KEY && process.env.STOREFRONT_SENDGRID_FROM) {
  notificationProviders.push({
    resolve: "@medusajs/medusa/notification-sendgrid",
    id: "storefront-sendgrid",
    options: {
      channels: ["email"],
      api_key: process.env.STOREFRONT_SENDGRID_API_KEY,
      from: process.env.STOREFRONT_SENDGRID_FROM,
    },
  })
} else if (process.env.NODE_ENV !== "production") {
  notificationProviders.push({
    resolve: "@medusajs/medusa/notification-local",
    id: "storefront-local-email",
    options: { channels: ["email"] },
  })
}

modules.push({
  resolve: "@medusajs/medusa/notification",
  options: { providers: notificationProviders },
})

modules.push({
  resolve: "@medusajs/medusa/fulfillment",
  options: { providers: [{ resolve: "./src/modules/storefront-fulfillment", id: "storefront" }] },
})

const paymentProviders: Record<string, unknown>[] = []
if (testPaymentEnabled()) {
  paymentProviders.push({ resolve: "./src/modules/storefront-test-payment", id: "local" })
}
if (peachPaymentEnabled()) {
  modules.push({ resolve: "./src/modules/storefront-peach" })
  paymentProviders.push({ resolve: "./src/modules/storefront-peach-payment-provider", id: "sandbox" })
}
if (paymentProviders.length) {
  modules.push({
    resolve: "@medusajs/medusa/payment",
    options: { providers: paymentProviders },
  })
}

modules.push({
  resolve: "@medusajs/medusa/file",
  options: {
    providers: [{
      resolve: "@medusajs/medusa/file-local",
      id: "local",
      options: hostedLocalFileOptions(process.env),
    }],
  },
})

module.exports = defineConfig({
  projectConfig: {
    databaseUrl: process.env.DATABASE_URL,
    redisUrl: process.env.REDIS_URL,
    workerMode: "shared",
    http: {
      storeCors: process.env.STORE_CORS || "http://localhost:3004",
      adminCors: process.env.ADMIN_CORS || "http://localhost:9000",
      authCors: process.env.AUTH_CORS || "http://localhost:9000,http://localhost:3004",
      jwtSecret: process.env.JWT_SECRET,
      cookieSecret: process.env.COOKIE_SECRET,
      authMethodsPerActor: {
        user: ["emailpass"],
        customer: ["storefront-clerk"],
      },
    }
  },
  modules: [
    ...modules,
    {
      resolve: "@medusajs/medusa/auth",
      options: {
        providers: [
          { resolve: "@medusajs/medusa/auth-emailpass", id: "emailpass" },
          { resolve: "./src/modules/storefront-clerk-auth", id: "storefront-clerk" },
        ],
      },
    },
  ],
})
