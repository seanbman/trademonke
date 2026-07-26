FROM node:22-alpine AS build
WORKDIR /gui
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /gui/dist /usr/share/nginx/html
