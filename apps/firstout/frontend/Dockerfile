# Repo-root build context. npm workspaces require every workspace package.json
# present for `npm ci`; this image does not copy libs/ui source (Carbon, not kit).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY vendor/braces/braces-3.0.4-f0rge.1.tgz ./vendor/braces/
COPY apps/marrow/frontend/package.json ./apps/marrow/frontend/
COPY apps/dk/tag-printer/frontend/package.json ./apps/dk/tag-printer/frontend/
COPY apps/firstout/frontend/package.json ./apps/firstout/frontend/
COPY apps/storefront/commerce/package.json ./apps/storefront/commerce/
COPY apps/storefront/web/package.json ./apps/storefront/web/
COPY libs/ui/package.json ./libs/ui/
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY apps/firstout/frontend ./apps/firstout/frontend

ARG API_URL=http://localhost:8003
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED=false
ENV API_URL=$API_URL
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED=$NEXT_PUBLIC_TENANT_SUBDOMAINS_ENABLED
ENV NODE_OPTIONS=--max-old-space-size=1536
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
RUN npm run typecheck -w firstout-frontend
RUN npm run build -w firstout-frontend

FROM node:22-alpine AS runner
WORKDIR /app

ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/F0rge/f0rge" \
      org.opencontainers.image.revision=$SOURCE_COMMIT \
      org.opencontainers.image.title="Firstout frontend"

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/firstout/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/firstout/frontend/.next/static ./apps/firstout/frontend/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/firstout/frontend/public ./apps/firstout/frontend/public

USER nextjs

EXPOSE 3000
ENV PORT=3000

CMD ["node", "apps/firstout/frontend/server.js"]
