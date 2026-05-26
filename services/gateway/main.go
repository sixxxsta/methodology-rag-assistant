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

	authHandlers := &auth.Handlers{
		Store:      userStore,
		Issuer:     issuer,
		AdminEmail: cfg.AdminEmail,
	}
	if cfg.AdminEmail != "" {
		fmt.Fprintf(os.Stdout, "Admin account: %s\n", cfg.AdminEmail)
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

	server := api.NewHTTPServer(ragClient, authHandlers, adminHandlers, issuer, cfg.AdminEmail, coreProxy)

	fmt.Fprintf(os.Stdout, "Gateway API listening on %s\n", cfg.HTTPAddr)
	return http.ListenAndServe(cfg.HTTPAddr, server.Handler())
}
