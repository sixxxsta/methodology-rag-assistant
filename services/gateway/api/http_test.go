package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"methodology-rag-assistant/auth"
	"methodology-rag-assistant/rag"
)

type mockRAG struct {
	err error
}

func (m *mockRAG) Chat(_ context.Context, message, _, _ string) (rag.ChatResult, error) {
	if m.err != nil {
		return rag.ChatResult{}, m.err
	}
	return rag.ChatResult{SessionID: "s1", Answer: "ok: " + message}, nil
}

func (m *mockRAG) Feedback(context.Context, rag.FeedbackPayload) error { return nil }
func (m *mockRAG) Health(context.Context) (map[string]any, error) {
	return map[string]any{"status": "ok"}, nil
}
func (m *mockRAG) Ingest(context.Context) (rag.IngestResult, error) {
	return rag.IngestResult{Files: 1, Chunks: 5}, nil
}

func testServer(t *testing.T) (*HTTPServer, string) {
	t.Helper()
	store, err := auth.NewStore(filepath.Join(t.TempDir(), "test.db"))
	if err != nil {
		t.Fatal(err)
	}
	issuer, err := auth.NewTokenIssuer("test-secret-key-32chars-min", 24)
	if err != nil {
		t.Fatal(err)
	}
	user, err := store.CreateUser("u@test.com", "secret12", auth.RoleUser)
	if err != nil {
		t.Fatal(err)
	}
	token, err := issuer.Sign(user)
	if err != nil {
		t.Fatal(err)
	}
	h := &auth.Handlers{Store: store, Issuer: issuer}
	srv := NewHTTPServer(&mockRAG{}, h, nil, issuer)
	t.Cleanup(func() { _ = store.Close() })
	return srv, token
}

func TestHTTPServerChatRequiresAuth(t *testing.T) {
	srv, token := testServer(t)

	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewBufferString(`{"message":"hi"}`))
	req.Header.Set("Authorization", "Bearer "+token)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rr.Code, rr.Body.String())
	}
}

func TestHTTPServerChatUnauthorized(t *testing.T) {
	srv, _ := testServer(t)
	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewBufferString(`{"message":"hi"}`))
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rr.Code)
	}
}

func TestHTTPServerChatError(t *testing.T) {
	store, err := auth.NewStore(filepath.Join(t.TempDir(), "e.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })
	issuer, _ := auth.NewTokenIssuer("test-secret-key-32chars-min", 24)
	_ = store
	token, _ := issuer.Sign(&auth.User{ID: 1, Email: "a@b.c", Role: auth.RoleUser})

	srv := NewHTTPServer(&mockRAG{err: errors.New("down")}, &auth.Handlers{Store: store, Issuer: issuer}, nil, issuer)
	req := httptest.NewRequest(http.MethodPost, "/api/chat", bytes.NewBufferString(`{"message":"x"}`))
	req.Header.Set("Authorization", "Bearer "+token)
	rr := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rr, req)
	if rr.Code != http.StatusInternalServerError {
		t.Fatalf("expected 500, got %d", rr.Code)
	}
	_ = json.NewDecoder(rr.Body)
}
