package auth

import (
	"encoding/json"
	"net/http"
)

type Handlers struct {
	Store      *Store
	Issuer     *TokenIssuer
	AdminEmail string
}

type registerRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (h *Handlers) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}

	role := h.roleForEmail(req.Email)

	user, err := h.Store.CreateUser(req.Email, req.Password, role)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	token, err := h.Issuer.Sign(user)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "token error"})
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{
		"token": token,
		"user":  user,
	})
}

func (h *Handlers) Login(w http.ResponseWriter, r *http.Request) {
	var req loginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}

	user, err := h.Store.Authenticate(req.Email, req.Password)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": err.Error()})
		return
	}

	user, err = h.syncUserRole(user)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "role sync failed"})
		return
	}

	token, err := h.Issuer.Sign(user)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "token error"})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"token": token,
		"user":  user,
	})
}

func (h *Handlers) Me(w http.ResponseWriter, r *http.Request) {
	claims, ok := ClaimsFromContext(r.Context())
	if !ok {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
		return
	}
	user, err := h.Store.GetByID(claims.UserID)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "user not found"})
		return
	}
	user, err = h.syncUserRole(user)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "role sync failed"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"user": user})
}

func (h *Handlers) roleForEmail(email string) string {
	if h.AdminEmail != "" && normalizeEmail(email) == normalizeEmail(h.AdminEmail) {
		return RoleAdmin
	}
	return RoleUser
}

func (h *Handlers) syncUserRole(user *User) (*User, error) {
	expected := h.roleForEmail(user.Email)
	if user.Role == expected {
		return user, nil
	}
	return h.Store.UpdateRole(user.ID, expected)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
