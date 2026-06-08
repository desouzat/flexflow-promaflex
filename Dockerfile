# Stage 1: Build the React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy frontend dependency locks
COPY frontend/package*.json ./
COPY frontend/.npmrc ./

# Install packages exactly (ignore unsafe lifecycle scripts)
RUN npm install --ignore-scripts

# Copy frontend source code and build it
COPY frontend/ ./
RUN npm run build

# Stage 2: Setup Python & Nginx
FROM python:3.11-slim

# Install Nginx and utility packages (curl for health check, procps for management)
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source code
COPY backend/ ./backend/

# Copy built React frontend static files to Nginx
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy startup boot script
COPY start.sh ./
# Fix Windows CRLF line endings in start.sh and make it executable
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Expose port 8080 for Cloud Run compatibility
EXPOSE 8080

# Run entrypoint sequence
CMD ["./start.sh"]
