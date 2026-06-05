package auth

import (
	"path/filepath"
	"testing"
)

func TestResolveRole(t *testing.T) {
	h := &Handlers{AdminEmail: "admin@example.com"}

	user := &User{Email: "admin@example.com", Role: RoleStudent}
	if got := h.resolveRole(user); got != RoleAdmin {
		t.Fatalf("expected admin, got %s", got)
	}

	user = &User{Email: "curator@example.com", Role: RoleUser}
	if got := h.resolveRole(user); got != RoleCurator {
		t.Fatalf("expected curator (legacy user), got %s", got)
	}

	user = &User{Email: "student@example.com", Role: RoleStudent}
	if got := h.resolveRole(user); got != RoleStudent {
		t.Fatalf("expected student, got %s", got)
	}
}

func TestRegisterCreatesStudent(t *testing.T) {
	store, err := NewStore(filepath.Join(t.TempDir(), "users.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })

	h := &Handlers{Store: store, AdminEmail: "admin@example.com"}
	if err := h.validateStudentRegistration("student@example.com"); err != nil {
		t.Fatal(err)
	}

	user, err := store.CreateUser("student@example.com", "secret12", RoleStudent, "Студент Тест")
	if err != nil {
		t.Fatal(err)
	}
	if user.Role != RoleStudent {
		t.Fatalf("stored role = %s, want student", user.Role)
	}
}

func TestRegisterRejectsAdminEmail(t *testing.T) {
	h := &Handlers{AdminEmail: "admin@example.com"}
	if err := h.validateStudentRegistration("admin@example.com"); err == nil {
		t.Fatal("expected registration to be rejected for admin email")
	}
}

func TestSyncUserRoleDemotesFormerAdmin(t *testing.T) {
	store, err := NewStore(filepath.Join(t.TempDir(), "users.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })

	user, err := store.CreateUser("was@example.com", "secret12", RoleAdmin, "Бывший Админ")
	if err != nil {
		t.Fatal(err)
	}

	h := &Handlers{Store: store, AdminEmail: "real@example.com"}
	updated, err := h.syncUserRole(user)
	if err != nil {
		t.Fatal(err)
	}
	if updated.Role != RoleAdmin {
		t.Fatalf("role = %s, want admin preserved when not matching ADMIN_EMAIL", updated.Role)
	}

	user2, err := store.CreateUser("real@example.com", "secret12", RoleStudent, "Реальный Админ")
	if err != nil {
		t.Fatal(err)
	}
	updated2, err := h.syncUserRole(user2)
	if err != nil {
		t.Fatal(err)
	}
	if updated2.Role != RoleAdmin {
		t.Fatalf("role = %s, want admin after sync for ADMIN_EMAIL", updated2.Role)
	}
}
