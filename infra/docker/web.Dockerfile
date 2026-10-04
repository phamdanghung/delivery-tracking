FROM node:22-bookworm-slim
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/admin-web/package.json apps/admin-web/package.json
COPY apps/driver-mobile/package.json apps/driver-mobile/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN npm ci
COPY apps/admin-web apps/admin-web
COPY packages/shared packages/shared
RUN npm run build:web && chown -R node:node /workspace/apps/admin-web/.next
USER node
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@fleet/admin-web"]
