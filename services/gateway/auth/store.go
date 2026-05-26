package auth

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite"
	"golang.org/x/crypto/bcrypt"
)

const (
	RoleUser  = "user"
	RoleAdmin = "admin"
)

type User struct {
	ID        int64     `json:"id"`
	Email     string    `json:"email"`
	Role      string    `json:"role"`
	CreatedAt time.Time `json:"created_at"`
}

type Store struct {
	db *sql.DB
}

func NewStore(dbPath string) (*Store, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	s := &Store{db: db}
	if err := s.migrate(); err != nil {
		_ = db.Close()
		return nil, err
	}
	return s, nil
}

func (s *Store) Close() error {
	return s.db.Close()
}

func (s *Store) migrate() error {
	_, err := s.db.Exec(`
		CREATE TABLE IF NOT EXISTS users (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			email TEXT NOT NULL UNIQUE COLLATE NOCASE,
			password_hash TEXT NOT NULL,
			role TEXT NOT NULL DEFAULT 'user',
			created_at TEXT NOT NULL
		);
	`)
	return err
}

func (s *Store) CountUsers() (int, error) {
	var n int
	err := s.db.QueryRow(`SELECT COUNT(*) FROM users`).Scan(&n)
	return n, err
}

func (s *Store) CreateUser(email, password, role string) (*User, error) {
	email = normalizeEmail(email)
	if email == "" || len(password) < 6 {
		return nil, fmt.Errorf("email required and password min 6 chars")
	}
	if role != RoleUser && role != RoleAdmin {
		role = RoleUser
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC().Format(time.RFC3339)
	res, err := s.db.Exec(
		`INSERT INTO users (email, password_hash, role, created_at) VALUES (?, ?, ?, ?)`,
		email, string(hash), role, now,
	)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			return nil, fmt.Errorf("email already registered")
		}
		return nil, err
	}
	id, _ := res.LastInsertId()
	return s.GetByID(id)
}

func (s *Store) Authenticate(email, password string) (*User, error) {
	email = normalizeEmail(email)
	var id int64
	var hash, role, createdAt string
	err := s.db.QueryRow(
		`SELECT id, password_hash, role, created_at FROM users WHERE email = ?`,
		email,
	).Scan(&id, &hash, &role, &createdAt)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("invalid email or password")
	}
	if err != nil {
		return nil, err
	}
	if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)); err != nil {
		return nil, fmt.Errorf("invalid email or password")
	}
	t, _ := time.Parse(time.RFC3339, createdAt)
	return &User{ID: id, Email: email, Role: role, CreatedAt: t}, nil
}

func (s *Store) UpdateRole(id int64, role string) (*User, error) {
	if role != RoleUser && role != RoleAdmin {
		role = RoleUser
	}
	_, err := s.db.Exec(`UPDATE users SET role = ? WHERE id = ?`, role, id)
	if err != nil {
		return nil, err
	}
	return s.GetByID(id)
}

func (s *Store) GetByID(id int64) (*User, error) {
	var email, role, createdAt string
	err := s.db.QueryRow(
		`SELECT email, role, created_at FROM users WHERE id = ?`, id,
	).Scan(&email, &role, &createdAt)
	if err != nil {
		return nil, err
	}
	t, _ := time.Parse(time.RFC3339, createdAt)
	return &User{ID: id, Email: email, Role: role, CreatedAt: t}, nil
}

func normalizeEmail(e string) string {
	return strings.ToLower(strings.TrimSpace(e))
}
