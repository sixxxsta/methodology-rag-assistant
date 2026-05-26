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
	HTTPAddr           string
	RAGServiceURL      string
	RAGTimeout         time.Duration
	RAGInternalSecret  string
	AuthDBPath         string
	JWTSecret          string
	JWTTTLHours        int
	AdminEmail         string
	KnowledgeDir       string
	CoreServiceURL     string
	CoreInternalSecret string
}

func Load() (Config, error) {
	if err := loadDotEnv(); err != nil {
		return Config{}, err
	}

	jwtSecret := strings.TrimSpace(os.Getenv("JWT_SECRET"))
	if jwtSecret == "" {
		return Config{}, fmt.Errorf("JWT_SECRET is required")
	}

	return Config{
		HTTPAddr:          envOrDefault("APP_HTTP_ADDR", ":8090"),
		RAGServiceURL:     strings.TrimRight(envOrDefault("RAG_SERVICE_URL", "http://127.0.0.1:8100"), "/"),
		RAGTimeout:        durationFromEnv("RAG_TIMEOUT_SECONDS", 120),
		RAGInternalSecret: strings.TrimSpace(os.Getenv("RAG_INTERNAL_SECRET")),
		AuthDBPath:        envOrDefault("AUTH_DB_PATH", "/app/data/users.db"),
		JWTSecret:         jwtSecret,
		JWTTTLHours:       intFromEnv("JWT_TTL_HOURS", 72),
		AdminEmail:        resolveAdminEmail(),
		KnowledgeDir:       envOrDefault("KNOWLEDGE_DIR", "/knowledge"),
		CoreServiceURL:     strings.TrimRight(envOrDefault("CORE_SERVICE_URL", "http://127.0.0.1:8200"), "/"),
		CoreInternalSecret: strings.TrimSpace(os.Getenv("CORE_INTERNAL_SECRET")),
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

func intFromEnv(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}

func envOrDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

// resolveAdminEmail returns the single admin account email (ADMIN_EMAIL).
// Falls back to the first entry in legacy ADMIN_EMAILS for compatibility.
func resolveAdminEmail() string {
	if v := strings.TrimSpace(os.Getenv("ADMIN_EMAIL")); v != "" {
		return strings.ToLower(v)
	}
	raw := strings.TrimSpace(os.Getenv("ADMIN_EMAILS"))
	if raw == "" {
		return ""
	}
	for _, part := range strings.Split(raw, ",") {
		if e := strings.ToLower(strings.TrimSpace(part)); e != "" {
			return e
		}
	}
	return ""
}
