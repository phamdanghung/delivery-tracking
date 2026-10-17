FROM node:22-bookworm-slim AS builder
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/admin-web/package.json apps/admin-web/package.json
COPY apps/driver-mobile/package.json apps/driver-mobile/package.json
COPY packages/shared/package.json packages/shared/package.json
COPY scripts/patch_query_string_interop.cjs scripts/patch_query_string_interop.cjs
RUN npm install --global npm@12.2.0 && npm ci
COPY apps/admin-web apps/admin-web
COPY packages/shared packages/shared
RUN npm run build:web && mkdir -p apps/admin-web/public

FROM node:22-bookworm-slim AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /workspace
COPY --from=builder /workspace/apps/admin-web/.next/standalone ./
COPY --from=builder /workspace/apps/admin-web/.next/static ./apps/admin-web/.next/static
COPY --from=builder /workspace/apps/admin-web/public ./apps/admin-web/public
RUN mkdir -p apps/admin-web/.next/cache && chown node:node apps/admin-web/.next/cache
USER node
EXPOSE 3000
CMD ["node", "apps/admin-web/server.js"]
