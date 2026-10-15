# IORP frontend — production image (PHASE-4). Multi-stage: npm ci → next build (standalone) → minimal runtime.
# The browser calls /api/v1 on this same origin; the Next server forwards it to BACKEND_URL. Next fixes rewrites at
# build time, so BACKEND_URL is a build argument (the Compose service name, identical in staging and production).
# No secrets: nothing here is NEXT_PUBLIC except the optional idle timeout.

ARG NODE_IMAGE=node:24-alpine@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ARG BACKEND_URL=http://backend:8080
ARG NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES=
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=standalone \
    BACKEND_URL=${BACKEND_URL} \
    NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES=${NEXT_PUBLIC_IDLE_TIMEOUT_MINUTES}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build \
 && mkdir -p public

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.status<500?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
