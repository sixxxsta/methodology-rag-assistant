package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	HTTPAddr         string
	RAGServiceURL    string
	RAGTimeout       time.Duration
	StaticDir string
}

func Load() (Config, error) {
	if err := loadDotEnv(); err != nil {
		return Config{}, err
	}

	ragURL := envOrDefault("RAG_SERVICE_URL", "http://127.0.0.1:8100")

	return Config{
		HTTPAddr:      envOrDefault("APP_HTTP_ADDR", ":8090"),
		RAGServiceURL: strings.TrimRight(ragURL, "/"),
		RAGTimeout:    durationFromEnv("RAG_TIMEOUT_SECONDS", 120),
		StaticDir:     envOrDefault("STATIC_DIR", "web"),
	}, nil
}

func loadDotEnv() error {
	candidates := []string{".env"}
	if root := findProjectRoot(); root != "" {
		candidates = append([]string{filepath.Join(root, ".env")}, candidates...)
	}
	for _, path := range candidates {
		if err := godotenv.Load(path); err == nil {
			return nil
		} else if !os.IsNotExist(err) {
			return fmt.Errorf("load %s: %w", path, err)
		}
	}
	return nil
}

func findProjectRoot() string {
	dir, err := os.Getwd()
	if err != nil {
		return ""
	}
	for {
		if _, err := os.Stat(filepath.Join(dir, "docker-compose.yml")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
		dir = parent
	}
}

func durationFromEnv(key string, defaultSeconds int) time.Duration {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return time.Duration(defaultSeconds) * time.Second
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed <= 0 {
		return time.Duration(defaultSeconds) * time.Second
	}
	return time.Duration(parsed) * time.Second
}

func envOrDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}
