package main

import (
	"fmt"
	"net/http"
	"os"

	"methodology-rag-assistant/admin"
	"methodology-rag-assistant/api"
	"methodology-rag-assistant/auth"
	"methodology-rag-assistant/config"
	"methodology-rag-assistant/core"
	"methodology-rag-assistant/rag"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load()
	if err != nil {
		return err
	}

	userStore, err := auth.NewStore(cfg.AuthDBPath)
	if err != nil {
		return fmt.Errorf("auth db: %w", err)
	}
	defer userStore.Close()

	issuer, err := auth.NewTokenIssuer(cfg.JWTSecret, cfg.JWTTTLHours)
	if err != nil {
		return err
	}

	ragClient := rag.NewClient(cfg.RAGServiceURL, &http.Client{Timeout: cfg.RAGTimeout}, cfg.RAGInternalSecret)

	if err := auth.EnsureAdmin(userStore, cfg.AdminEmail, cfg.AdminPassword); err != nil {
		return fmt.Errorf("bootstrap admin: %w", err)
	}

	authHandlers := &auth.Handlers{
		Store:           userStore,
		Issuer:          issuer,
		AdminEmail:      cfg.AdminEmail,
		CoreServiceURL:  cfg.CoreServiceURL,
		CoreInternalKey: cfg.CoreInternalSecret,
	}
	if cfg.AdminEmail != "" {
		fmt.Fprintf(os.Stdout, "Admin account: %s\n", cfg.AdminEmail)
		if cfg.AdminPassword == "" {
			fmt.Fprintln(os.Stdout, "Warning: ADMIN_PASSWORD not set — create admin via POST /api/admin/users or set password in .env")
		}
	} else {
		fmt.Fprintln(os.Stdout, "Warning: ADMIN_EMAIL is not set — admin panel will be unavailable")
	}
	adminHandlers := &admin.Handlers{
		KnowledgeDir: cfg.KnowledgeDir,
		RAG:          ragClient,
	}

	var coreProxy *core.Proxy
	if cfg.CoreServiceURL != "" {
		var err error
		coreProxy, err = core.NewProxy(cfg.CoreServiceURL, cfg.CoreInternalSecret)
		if err != nil {
			return fmt.Errorf("core proxy: %w", err)
		}
		fmt.Fprintf(os.Stdout, "Core API proxy → %s (/api/ed/*)\n", cfg.CoreServiceURL)
	}

	server := api.NewHTTPServer(
		ragClient, authHandlers, adminHandlers, issuer,
		cfg.AdminEmail, cfg.CoreServiceURL, coreProxy,
		cfg.RateLimitRegister, cfg.RateLimitChat,
	)

	fmt.Fprintf(os.Stdout, "Gateway API listening on %s\n", cfg.HTTPAddr)
	return http.ListenAndServe(cfg.HTTPAddr, server.Handler())
}
