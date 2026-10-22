# Сборка из корня репозитория: docker compose (см. docker-compose.yml) делает это сам
FROM node:22-alpine
WORKDIR /srv
COPY cloud/function/index.js cloud/function/acl.js cloud/function/auth.js cloud/function/store.js app/
COPY src/hr-metrics.html app/static/page.html
COPY src/iway-portal.html app/static/portal.html
COPY server/server.js ./
ENV NODE_ENV=production NODE_NO_WARNINGS=1 DATA_DIR=/data PORT=8080
USER node
EXPOSE 8080
CMD ["node", "server.js"]
