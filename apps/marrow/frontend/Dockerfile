# Repo-root build context: mirror the monorepo layout so the app builds at the
# same relative path as in the repo (apps/marrow/frontend). With
# outputFileTracingRoot pinned to the repo root in next.config.ts, the
# standalone output nests the server under apps/marrow/frontend/.
FROM node:22-alpine AS deps
WORKDIR /app
# npm workspaces: one root lockfile, one `npm ci` at the root. Copy each
# workspace's package.json path-preserving so npm can resolve the tree.
COPY package.json package-lock.json ./
COPY apps/marrow/frontend/package.json ./apps/marrow/frontend/
COPY libs/ui/package.json ./libs/ui/
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY libs/ui ./libs/ui
COPY apps/marrow/frontend ./apps/marrow/frontend

ARG API_URL=http://backend:8000
ENV API_URL=$API_URL

# ponytail: cap the build heap so `next build` GCs instead of getting OOM-killed
# on the remote Fly builder when it races the backend build. Raise if needed.
ENV NODE_OPTIONS=--max-old-space-size=1536
RUN npm run build -w frontend

FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# With outputFileTracingRoot at the repo root, .next/standalone contains the
# mirrored tree: the server entry is apps/marrow/frontend/server.js, and static
# assets / public must be placed at the matching nested paths (Next copies
# neither into standalone automatically).
COPY --from=builder --chown=nextjs:nodejs /app/apps/marrow/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/marrow/frontend/.next/static ./apps/marrow/frontend/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/marrow/frontend/public ./apps/marrow/frontend/public

USER nextjs

EXPOSE 3000
ENV PORT=3000

CMD ["node", "apps/marrow/frontend/server.js"]
