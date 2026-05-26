package rag

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type HTTPDoer interface {
	Do(req *http.Request) (*http.Response, error)
}

type Service interface {
	Chat(ctx context.Context, message, sessionID, language string) (ChatResult, error)
	Feedback(ctx context.Context, payload FeedbackPayload) error
	Health(ctx context.Context) (map[string]any, error)
	Ingest(ctx context.Context) (IngestResult, error)
}

type Client struct {
	baseURL        string
	httpClient     HTTPDoer
	internalSecret string
}

func NewClient(baseURL string, httpClient HTTPDoer, internalSecret string) *Client {
	return &Client{
		baseURL:        strings.TrimRight(baseURL, "/"),
		httpClient:     httpClient,
		internalSecret: internalSecret,
	}
}

type IngestResult struct {
	Files        int    `json:"files"`
	Chunks       int    `json:"chunks"`
	Collection   string `json:"collection"`
	TotalPoints  int    `json:"total_points"`
}

type Source struct {
	Source     string  `json:"source"`
	Score      float64 `json:"score"`
	ChunkIndex int     `json:"chunk_index"`
	Excerpt    string  `json:"excerpt"`
}

type ChatResult struct {
	SessionID string   `json:"session_id"`
	Answer    string   `json:"answer"`
	Sources   []Source `json:"sources"`
}

type FeedbackPayload struct {
	SessionID string `json:"session_id"`
	Rating    int    `json:"rating"`
	Comment   string `json:"comment"`
	Question  string `json:"question"`
	Answer    string `json:"answer"`
}

type chatRequest struct {
	Message   string `json:"message"`
	SessionID string `json:"session_id,omitempty"`
	Language  string `json:"language,omitempty"`
}

func (c *Client) Chat(ctx context.Context, message, sessionID, language string) (ChatResult, error) {
	body, err := json.Marshal(chatRequest{Message: message, SessionID: sessionID, Language: language})
	if err != nil {
		return ChatResult{}, fmt.Errorf("marshal chat request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/chat", bytes.NewReader(body))
	if err != nil {
		return ChatResult{}, fmt.Errorf("build chat request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return ChatResult{}, fmt.Errorf("call rag service: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return ChatResult{}, fmt.Errorf("read chat response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return ChatResult{}, fmt.Errorf("rag service returned %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	var parsed ChatResult
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return ChatResult{}, fmt.Errorf("decode chat response: %w", err)
	}
	if strings.TrimSpace(parsed.Answer) == "" {
		return ChatResult{}, fmt.Errorf("rag service returned empty answer")
	}
	return parsed, nil
}

func (c *Client) Feedback(ctx context.Context, payload FeedbackPayload) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal feedback: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/feedback", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("build feedback request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("call rag feedback: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("rag feedback returned %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}
	return nil
}

func (c *Client) Ingest(ctx context.Context) (IngestResult, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/ingest", nil)
	if err != nil {
		return IngestResult{}, err
	}
	if c.internalSecret != "" {
		req.Header.Set("X-RAG-Internal-Key", c.internalSecret)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return IngestResult{}, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return IngestResult{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return IngestResult{}, fmt.Errorf("ingest returned %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}

	var parsed IngestResult
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return IngestResult{}, err
	}
	return parsed, nil
}

func (c *Client) Health(ctx context.Context) (map[string]any, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.baseURL+"/health", nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("health returned %d", resp.StatusCode)
	}
	var parsed map[string]any
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return nil, err
	}
	return parsed, nil
}
