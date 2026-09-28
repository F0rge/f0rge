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
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY apps/storefront/web/package.json ./apps/storefront/web/
COPY libs/ui/package.json ./libs/ui/
COPY libs/ui ./libs/ui
COPY apps/storefront/web ./apps/storefront/web
ENV NODE_OPTIONS=--max-old-space-size=1536
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
