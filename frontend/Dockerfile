# ─────────────────────────────────────────────────────────────────────────────
# Production Dockerfile — Next.js (multi-stage)
#
# Stage 1 (builder): Install all deps + run `next build`
# Stage 2 (runner):  Minimal runtime image using the standalone output
#
# next.config.js sets `output: 'standalone'`, which emits a self-contained
# Node.js server under .next/standalone — no node_modules in the final layer.
# Final image is ~3× smaller than a naive single-stage build.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Install all dependencies (including devDeps needed for the build)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy full source and build
COPY . .
RUN npm run build

# ── Stage 2: Production runtime ───────────────────────────────────────────────
FROM node:18-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
# Disable Next.js telemetry in production
ENV NEXT_TELEMETRY_DISABLED=1

# The standalone output bundles a minimal server.js + required node_modules.
# Static assets and public/ are NOT included automatically — copy separately.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
