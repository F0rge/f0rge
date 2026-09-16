# Repo-root build context. npm workspaces require every workspace package.json
# present for `npm ci`; this image does not copy libs/ui source (landing is not kit).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/marrow/frontend/package.json ./apps/marrow/frontend/
COPY apps/dk/tag-printer/frontend/package.json ./apps/dk/tag-printer/frontend/
COPY apps/vellano/frontend/package.json ./apps/vellano/frontend/
COPY apps/vellano/landing/package.json ./apps/vellano/landing/
COPY libs/ui/package.json ./libs/ui/
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY apps/vellano/landing ./apps/vellano/landing

ARG API_URL=http://localhost:8003
ENV API_URL=$API_URL
ARG NEXT_PUBLIC_TENANT_BASE_DOMAIN=localhost
ENV NEXT_PUBLIC_TENANT_BASE_DOMAIN=$NEXT_PUBLIC_TENANT_BASE_DOMAIN
ENV NODE_OPTIONS=--max-old-space-size=1536
RUN npm run typecheck -w vellano-landing
RUN npm run build -w vellano-landing

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/vellano/landing/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/vellano/landing/.next/static ./apps/vellano/landing/.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000

CMD ["node", "apps/vellano/landing/server.js"]
