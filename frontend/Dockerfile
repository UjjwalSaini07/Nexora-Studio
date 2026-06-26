# frontend/Dockerfile
# Multi-stage build: install deps, build the production bundle, then run
# it from a slim runtime image without retaining the full node_modules dev
# closure or build cache layers.

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* vars must be present at BUILD time (they're inlined into
# the client bundle), so accept it as a build arg with a sane default.
ARG NEXT_PUBLIC_BOT_URL=http://localhost:8080
ENV NEXT_PUBLIC_BOT_URL=${NEXT_PUBLIC_BOT_URL}
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
