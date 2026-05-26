package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"methodology-rag-assistant/rag"
)

type mockRAG struct {
	err error
}

func (m *mockRAG) Chat(_ context.Context, message, _, _ string) (rag.ChatResult, error) {
	if m.err != nil {
		return rag.ChatResult{}, m.err
	}
	return rag.ChatResult{
		SessionID: "sess-1",
		Answer:    "answer: " + message,
		Sources:   []rag.Source{{Source: "scrum.md", Score: 0.9}},
	}, nil
}

func (m *mockRAG) Feedback(context.Context, rag.FeedbackPayload) error { return nil }

func (m *mockRAG) Health(context.Context) (map[string]any, error) {
	return map[string]any{"status": "ok"}, nil
}

func TestHTTPServerChat(t *testing.T) {
	server := NewHTTPServer(&mockRAG{}, "")

	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewBufferString(`{"message":"Scrum?"}`))
	rr := httptest.NewRecorder()
	server.Handler().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rr.Code, rr.Body.String())
	}

	var resp chatResponse
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.Answer == "" || resp.SessionID != "sess-1" {
		t.Fatalf("unexpected: %+v", resp)
	}
}

func TestHTTPServerChatError(t *testing.T) {
	server := NewHTTPServer(&mockRAG{err: errors.New("rag down")}, "")

	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewBufferString(`{"message":"x"}`))
	rr := httptest.NewRecorder()
	server.Handler().ServeHTTP(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", rr.Code)
	}
}
