FROM golang:1.25.5-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o rag-api .

FROM alpine:3.22

WORKDIR /app
COPY --from=builder /app/rag-api /app/rag-api
COPY --from=builder /app/web /app/web

EXPOSE 8090

ENTRYPOINT ["/app/rag-api"]
