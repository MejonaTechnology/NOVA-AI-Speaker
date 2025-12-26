FROM golang:1.22-alpine AS builder

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum* ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Download dependencies and generate go.sum
RUN go mod tidy

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -o nova-ai-backend .

# Final stage
FROM alpine:latest

WORKDIR /app

# Install ffmpeg for gTTS fallback
RUN apk add --no-cache ffmpeg

# Copy binary from builder
COPY --from=builder /app/nova-ai-backend .

# Expose port
EXPOSE 8001

# Run the application
CMD ["./nova-ai-backend"]
