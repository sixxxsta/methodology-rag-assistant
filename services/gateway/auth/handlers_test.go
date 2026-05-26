package auth

import (
	"path/filepath"
	"testing"
)

func TestRoleForEmail(t *testing.T) {
	h := &Handlers{AdminEmail: "admin@example.com"}

	if got := h.roleForEmail("admin@example.com"); got != RoleAdmin {
		t.Fatalf("expected admin, got %s", got)
	}
	if got := h.roleForEmail("Admin@Example.com"); got != RoleAdmin {
		t.Fatalf("expected admin (case insensitive), got %s", got)
	}
	if got := h.roleForEmail("user@example.com"); got != RoleUser {
		t.Fatalf("expected user, got %s", got)
	}
}

func TestRegisterFirstUserIsNotAdmin(t *testing.T) {
	store, err := NewStore(filepath.Join(t.TempDir(), "users.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })

	h := &Handlers{AdminEmail: "admin@example.com"}
	role := h.roleForEmail("first@example.com")
	if role != RoleUser {
		t.Fatalf("first registrant must be user, got %s", role)
	}

	user, err := store.CreateUser("first@example.com", "secret12", role)
	if err != nil {
		t.Fatal(err)
	}
	if user.Role != RoleUser {
		t.Fatalf("stored role = %s, want user", user.Role)
	}
}

func TestSyncUserRoleDemotesFormerAdmin(t *testing.T) {
	store, err := NewStore(filepath.Join(t.TempDir(), "users.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })

	user, err := store.CreateUser("was@example.com", "secret12", RoleAdmin)
	if err != nil {
		t.Fatal(err)
	}

	h := &Handlers{Store: store, AdminEmail: "real@example.com"}
	updated, err := h.syncUserRole(user)
	if err != nil {
		t.Fatal(err)
	}
	if updated.Role != RoleUser {
		t.Fatalf("role = %s, want user after sync", updated.Role)
	}
}
