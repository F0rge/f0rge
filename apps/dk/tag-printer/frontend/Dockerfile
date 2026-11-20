FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/marrow/frontend/package.json ./apps/marrow/frontend/
COPY apps/dk/tag-printer/frontend/package.json ./apps/dk/tag-printer/frontend/
COPY apps/firstout/frontend/package.json ./apps/firstout/frontend/
COPY libs/ui/package.json ./libs/ui/
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
# The whole install, not only /app/node_modules: npm nests some workspace
# dependencies (libs/ui/node_modules, the app's own node_modules).
COPY --from=deps /app ./
COPY package.json package-lock.json ./
COPY libs/ui ./libs/ui
COPY apps/dk/tag-printer/frontend ./apps/dk/tag-printer/frontend

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NODE_OPTIONS=--max-old-space-size=1536

RUN npm run build -w dk-tag-printer-frontend

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/dk/tag-printer/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/dk/tag-printer/frontend/.next/static ./apps/dk/tag-printer/frontend/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/dk/tag-printer/frontend/public ./apps/dk/tag-printer/frontend/public

USER nextjs

EXPOSE 3000
ENV PORT=3000
# Next standalone listens on $HOSTNAME, which Docker sets to the container id; 0.0.0.0 adds loopback for the check.
ENV HOSTNAME=0.0.0.0
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["node", "apps/dk/tag-printer/frontend/server.js"]
