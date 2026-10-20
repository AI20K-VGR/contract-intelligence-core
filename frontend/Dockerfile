# Build the browser bundle with environment values supplied by Compose.
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . ./

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_KEYCLOAK_URL=http://localhost:8080
ARG VITE_KEYCLOAK_REALM=contract-intelligence
ARG VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL} \
    VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM} \
    VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}

RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=6 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
