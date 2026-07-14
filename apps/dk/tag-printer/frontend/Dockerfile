FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/dk/tag-printer/frontend/package.json ./apps/dk/tag-printer/frontend/
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
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

CMD ["node", "apps/dk/tag-printer/frontend/server.js"]
