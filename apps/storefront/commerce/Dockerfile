# Build from the repository root so npm can resolve all declared workspaces.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY vendor/braces/braces-3.0.4-f0rge.1.tgz ./vendor/braces/
COPY apps/storefront/commerce/package.json ./apps/storefront/commerce/
RUN npm ci --workspace=@f0rge/storefront-commerce --include-workspace-root=false

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY apps/storefront/commerce/package.json ./apps/storefront/commerce/
COPY apps/storefront/commerce ./apps/storefront/commerce
ENV NODE_OPTIONS=--max-old-space-size=1536
# Nx runs the repository lint target in CI. The image installs only this
# workspace, so its build cannot load the root Nx ESLint configuration.
RUN npm run build --workspace @f0rge/storefront-commerce -- --lint false

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=9000
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/apps/storefront/commerce ./apps/storefront/commerce
WORKDIR /app/apps/storefront/commerce/.medusa/server
USER node
EXPOSE 9000
CMD ["node", "/app/node_modules/.bin/medusa", "start"]
