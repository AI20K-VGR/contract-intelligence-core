# Frontend as a static site, served inside ci-network; the edge Caddy
# (deploy/Caddyfile) terminates HTTPS and proxies $APP_HOST here.
#
# Build context is ./frontend (deploy/compose.frontend.yml). Vite bakes the
# VITE_* values into the bundle, so a change of API_HOST / AUTH_HOST needs a
# rebuild: deploy/deploy.sh does that on every run.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_KEYCLOAK_URL
ARG VITE_KEYCLOAK_REALM=contract-intelligence
ARG VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL \
    VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM \
    VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID
RUN test -n "$VITE_API_BASE_URL" && test -n "$VITE_KEYCLOAK_URL" && npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
# Client-side routes (/dossiers/…) have no file: answer them with index.html.
# Hashed bundles under /assets never change; index.html must always be fresh.
COPY <<'EOF' /etc/caddy/Caddyfile
{
	admin off
	auto_https off
}

:80 {
	root * /srv
	encode gzip

	@assets path /assets/*
	header @assets Cache-Control "public, max-age=31536000, immutable"
	@page not path /assets/*
	header @page Cache-Control "no-cache"

	try_files {path} /index.html
	file_server
}
EOF
