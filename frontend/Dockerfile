FROM node:18-slim

WORKDIR /app

# Install a simple static file server
RUN npm install -g serve

# Copy frontend files
COPY . .

EXPOSE 8080

# Serve static files on port 8080
CMD ["serve", "-s", ".", "-l", "8080"]
