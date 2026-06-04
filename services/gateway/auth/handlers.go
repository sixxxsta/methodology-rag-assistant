package auth

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
)

type Handlers struct {
	Store           *Store
	Issuer          *TokenIssuer
	AdminEmail      string
	CoreServiceURL  string
	CoreInternalKey string
}

type registerRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type createUserRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Role     string `json:"role"`
}

func (h *Handlers) Register(w http.ResponseWriter, r *http.Request) {
	var req registerRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}

	if err := h.validateStudentRegistration(req.Email); err != nil {
		writeJSON(w, http.StatusForbidden, map[string]string{"error": err.Error()})
		return
	}

	user, err := h.Store.CreateUser(req.Email, req.Password, RoleStudent)
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

func (h *Handlers) CreateUser(w http.ResponseWriter, r *http.Request) {
	var req createUserRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}

	role := NormalizeRole(req.Role)
	if role != RoleCurator && role != RoleAdmin {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "role must be curator or admin"})
		return
	}

	user, err := h.Store.CreateUser(req.Email, req.Password, role)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusCreated, map[string]any{"user": user})
}

type deleteAccountRequest struct {
	Password string `json:"password"`
}

func (h *Handlers) DeleteAccount(w http.ResponseWriter, r *http.Request) {
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
	if user.Role != RoleStudent {
		writeJSON(w, http.StatusForbidden, map[string]string{"error": "only student accounts can be self-deleted"})
		return
	}
	var req deleteAccountRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
		return
	}
	if _, err := h.Store.Authenticate(user.Email, req.Password); err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "invalid password"})
		return
	}
	if err := h.purgeCoreStudentData(r, user.Email); err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": err.Error()})
		return
	}
	if err := h.Store.DeleteUser(user.ID); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "delete failed"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (h *Handlers) purgeCoreStudentData(r *http.Request, email string) error {
	if h.CoreServiceURL == "" {
		return nil
	}
	req, err := http.NewRequestWithContext(
		r.Context(),
		http.MethodDelete,
		strings.TrimRight(h.CoreServiceURL, "/")+"/api/student/account-data",
		nil,
	)
	if err != nil {
		return err
	}
	req.Header.Set("X-User-Email", email)
	req.Header.Set("X-User-Role", RoleStudent)
	if h.CoreInternalKey != "" {
		req.Header.Set("X-Core-Internal-Key", h.CoreInternalKey)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return fmt.Errorf("core purge returned %d", resp.StatusCode)
	}
	return nil
}

func (h *Handlers) validateStudentRegistration(email string) error {
	normalized := normalizeEmail(email)
	if normalized == "" {
		return fmt.Errorf("email required")
	}
	if h.AdminEmail != "" && normalized == normalizeEmail(h.AdminEmail) {
		return fmt.Errorf("регистрация недоступна — войдите по выданным учётным данным")
	}
	existing, err := h.Store.GetByEmail(email)
	if err == nil {
		switch existing.Role {
		case RoleAdmin, RoleCurator:
			return fmt.Errorf("регистрация недоступна — войдите по выданным учётным данным")
		case RoleStudent:
			return fmt.Errorf("email already registered")
		}
	}
	return nil
}

func (h *Handlers) resolveRole(user *User) string {
	if h.AdminEmail != "" && normalizeEmail(user.Email) == normalizeEmail(h.AdminEmail) {
		return RoleAdmin
	}
	return NormalizeRole(user.Role)
}

func (h *Handlers) syncUserRole(user *User) (*User, error) {
	expected := h.resolveRole(user)
	if user.Role == expected {
		return user, nil
	}
	return h.Store.UpdateRole(user.ID, expected)
}

func EnsureAdmin(store *Store, adminEmail, adminPassword string) error {
	adminEmail = normalizeEmail(adminEmail)
	if adminEmail == "" || len(adminPassword) < 6 {
		return nil
	}
	_, err := store.GetByEmail(adminEmail)
	if err == nil {
		return nil
	}
	_, err = store.CreateUser(adminEmail, adminPassword, RoleAdmin)
	return err
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
