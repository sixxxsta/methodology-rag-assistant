FROM golang:1.25.5-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o gateway .

FROM alpine:3.21

RUN apk add --no-cache ca-certificates wget
COPY --from=builder /app/gateway /app/gateway

EXPOSE 8090

ENTRYPOINT ["/app/gateway"]
