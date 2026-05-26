package api

import (
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"methodology-rag-assistant/rag"
)

type HTTPServer struct {
	ragClient rag.Service
	staticDir string
}

func NewHTTPServer(ragClient rag.Service, staticDir string) *HTTPServer {
	return &HTTPServer{ragClient: ragClient, staticDir: staticDir}
}

func (s *HTTPServer) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /api/chat", s.handleChat)
	mux.HandleFunc("POST /api/feedback", s.handleFeedback)
	mux.HandleFunc("GET /api/health", s.handleHealth)
	mux.Handle("/", s.staticHandler())
	return mux
}

type chatRequest struct {
	Message   string `json:"message"`
	SessionID string `json:"session_id"`
	Language  string `json:"language"`
}

type chatResponse struct {
	SessionID string       `json:"session_id"`
	Answer    string       `json:"answer"`
	Sources   []rag.Source `json:"sources"`
}

type feedbackRequest struct {
	SessionID string `json:"session_id"`
	Rating    int    `json:"rating"`
	Comment   string `json:"comment"`
	Question  string `json:"question"`
	Answer    string `json:"answer"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func (s *HTTPServer) handleChat(w http.ResponseWriter, r *http.Request) {
	var req chatRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid json"})
		return
	}
	req.Message = strings.TrimSpace(req.Message)
	if req.Message == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "message is required"})
		return
	}

	result, err := s.ragClient.Chat(r.Context(), req.Message, strings.TrimSpace(req.SessionID), strings.TrimSpace(req.Language))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, errorResponse{Error: err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, chatResponse{
		SessionID: result.SessionID,
		Answer:    result.Answer,
		Sources:   result.Sources,
	})
}

func (s *HTTPServer) handleFeedback(w http.ResponseWriter, r *http.Request) {
	var req feedbackRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid json"})
		return
	}
	if req.Rating < 1 || req.Rating > 5 {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "rating must be 1..5"})
		return
	}

	err := s.ragClient.Feedback(r.Context(), rag.FeedbackPayload{
		SessionID: strings.TrimSpace(req.SessionID),
		Rating:    req.Rating,
		Comment:   strings.TrimSpace(req.Comment),
		Question:  strings.TrimSpace(req.Question),
		Answer:    strings.TrimSpace(req.Answer),
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, errorResponse{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *HTTPServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	data, err := s.ragClient.Health(r.Context())
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, errorResponse{Error: err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, data)
}

func (s *HTTPServer) staticHandler() http.Handler {
	dir := s.staticDir
	if _, err := os.Stat(dir); err != nil {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			http.NotFound(w, r)
		})
	}

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/" {
			http.ServeFile(w, r, filepath.Join(dir, "index.html"))
			return
		}
		path := filepath.Join(dir, filepath.Clean(r.URL.Path))
		if _, err := os.Stat(path); err == nil {
			http.ServeFile(w, r, path)
			return
		}
		http.ServeFile(w, r, filepath.Join(dir, "index.html"))
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
