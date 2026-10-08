# Multi-stage Dockerfile for Next.js 15 Frontend Dashboard
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci || npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN if [ -f package.json ] && grep -q '"build"' package.json; then npm run build; else mkdir -p .next; fi

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

COPY --from=builder /app ./

EXPOSE 3000
CMD ["npm", "start"]
