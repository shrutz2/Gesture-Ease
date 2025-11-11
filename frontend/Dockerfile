# Multi-stage build for React frontend
FROM node:18-alpine AS build

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci --silent

# Copy source and build
COPY public ./public
COPY src ./src
RUN npm run build

# Production stage with nginx
FROM nginx:stable-alpine

# Copy build files
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000



CMD ["nginx", "-g", "daemon off;"]