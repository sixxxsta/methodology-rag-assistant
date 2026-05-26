package main

import (
	"fmt"
	"net/http"
	"os"

	"methodology-rag-assistant/api"
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

	ragClient := rag.NewClient(cfg.RAGServiceURL, &http.Client{Timeout: cfg.RAGTimeout})
	server := api.NewHTTPServer(ragClient, cfg.StaticDir)

	fmt.Fprintf(os.Stdout, "Gateway listening on %s\n", cfg.HTTPAddr)
	return http.ListenAndServe(cfg.HTTPAddr, server.Handler())
}
