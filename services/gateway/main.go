package main

import (
	"fmt"
	"net/http"
	"os"

	"methodology-rag-assistant/admin"
	"methodology-rag-assistant/api"
	"methodology-rag-assistant/auth"
	"methodology-rag-assistant/config"
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
		Store:       userStore,
		Issuer:      issuer,
		AdminEmails: auth.ParseAdminEmails(cfg.AdminEmails),
	}
	adminHandlers := &admin.Handlers{
		KnowledgeDir: cfg.KnowledgeDir,
		RAG:          ragClient,
	}

	server := api.NewHTTPServer(ragClient, authHandlers, adminHandlers, issuer)

	fmt.Fprintf(os.Stdout, "Gateway API listening on %s\n", cfg.HTTPAddr)
	return http.ListenAndServe(cfg.HTTPAddr, server.Handler())
}
