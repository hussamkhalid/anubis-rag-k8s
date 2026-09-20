# ── build ──
FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# ── serve ──
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# nginx:alpine runs /docker-entrypoint.d/ templating: it substitutes env vars
# in *.template. Default upstream is the in-cluster service name.
ENV RAG_API_UPSTREAM=rag-api:8000
EXPOSE 8080
