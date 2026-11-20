# Build from the repository root so the npm workspace, shared UI package, and
# Next standalone tracing use the same paths as local development.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/storefront/web/package.json ./apps/storefront/web/
COPY libs/ui/package.json ./libs/ui/
RUN npm ci --workspace=@f0rge/storefront-web --include-workspace-root=false

FROM node:22-alpine AS builder
WORKDIR /app
# The whole install, not only /app/node_modules: npm nests some workspace
# dependencies (libs/ui/node_modules, the app's own node_modules).
COPY --from=deps /app ./
COPY package.json package-lock.json ./
COPY apps/storefront/web/package.json ./apps/storefront/web/
COPY libs/ui/package.json ./libs/ui/
COPY libs/ui ./libs/ui
COPY apps/storefront/web ./apps/storefront/web
ENV NODE_OPTIONS=--max-old-space-size=1536
# Public values Next bakes into the build (values: the deploy block's build.args). ARG, not ENV:
# one not passed stays unset, so server code still reads it at runtime instead of a baked "".
ARG NEXT_PUBLIC_BASE_URL
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
RUN npm run build --workspace @f0rge/storefront-web

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder --chown=nextjs:nodejs /app/apps/storefront/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/storefront/web/.next/static ./apps/storefront/web/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/storefront/web/public ./apps/storefront/web/public
USER nextjs
EXPOSE 3000
CMD ["node", "apps/storefront/web/server.js"]
