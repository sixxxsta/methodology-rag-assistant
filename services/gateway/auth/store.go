package auth

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"

	_ "modernc.org/sqlite"
	"golang.org/x/crypto/bcrypt"
)

const (
	RoleStudent = "student"
	RoleCurator = "curator"
	RoleAdmin   = "admin"
	// RoleUser is legacy — migrated to curator on login.
	RoleUser = "user"
)

type User struct {
	ID        int64     `json:"id"`
	Email     string    `json:"email"`
	Fio       string    `json:"fio"`
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
			role TEXT NOT NULL DEFAULT 'student',
			created_at TEXT NOT NULL
		);
	`)
	if err != nil {
		return err
	}
	_, _ = s.db.Exec(`ALTER TABLE users ADD COLUMN fio TEXT NOT NULL DEFAULT ''`)
	return nil
}

func (s *Store) CountUsers() (int, error) {
	var n int
	err := s.db.QueryRow(`SELECT COUNT(*) FROM users`).Scan(&n)
	return n, err
}

func NormalizeRole(role string) string {
	switch strings.ToLower(strings.TrimSpace(role)) {
	case RoleAdmin:
		return RoleAdmin
	case RoleCurator, RoleUser:
		return RoleCurator
	case RoleStudent:
		return RoleStudent
	default:
		return RoleStudent
	}
}

func validateFio(fio string) error {
	fio = strings.TrimSpace(fio)
	if len([]rune(fio)) < 2 {
		return fmt.Errorf("укажите ФИО (минимум 2 символа)")
	}
	return nil
}

func fixMojibake(value string) string {
	value = strings.TrimSpace(value)
	if value == "" || (!strings.Contains(value, "Ð") && !strings.Contains(value, "Ñ")) {
		return value
	}
	buf := make([]byte, 0, len(value))
	for _, r := range value {
		if r > 255 {
			return value
		}
		buf = append(buf, byte(r))
	}
	if !utf8.Valid(buf) {
		return value
	}
	fixed := string(buf)
	for _, r := range fixed {
		if r >= 0x0400 && r <= 0x04FF {
			return strings.TrimSpace(fixed)
		}
	}
	return value
}

func userFromRow(id int64, email, role, fio, createdAt string) *User {
	t, _ := time.Parse(time.RFC3339, createdAt)
	return &User{
		ID:        id,
		Email:     email,
		Fio:       fixMojibake(fio),
		Role:      NormalizeRole(role),
		CreatedAt: t,
	}
}

func (s *Store) CreateUser(email, password, role, fio string) (*User, error) {
	email = normalizeEmail(email)
	if email == "" || len(password) < 6 {
		return nil, fmt.Errorf("email required and password min 6 chars")
	}
	fio = fixMojibake(strings.TrimSpace(fio))
	if err := validateFio(fio); err != nil {
		return nil, err
	}
	role = NormalizeRole(role)
	if role != RoleStudent && role != RoleCurator && role != RoleAdmin {
		role = RoleStudent
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	now := time.Now().UTC().Format(time.RFC3339)
	res, err := s.db.Exec(
		`INSERT INTO users (email, password_hash, role, fio, created_at) VALUES (?, ?, ?, ?, ?)`,
		email, string(hash), role, fio, now,
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
	var hash, role, fio, createdAt string
	err := s.db.QueryRow(
		`SELECT id, password_hash, role, fio, created_at FROM users WHERE email = ?`,
		email,
	).Scan(&id, &hash, &role, &fio, &createdAt)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("invalid email or password")
	}
	if err != nil {
		return nil, err
	}
	if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)); err != nil {
		return nil, fmt.Errorf("invalid email or password")
	}
	return userFromRow(id, email, role, fio, createdAt), nil
}

func (s *Store) UpdateRole(id int64, role string) (*User, error) {
	role = NormalizeRole(role)
	_, err := s.db.Exec(`UPDATE users SET role = ? WHERE id = ?`, role, id)
	if err != nil {
		return nil, err
	}
	return s.GetByID(id)
}

func (s *Store) GetByID(id int64) (*User, error) {
	var email, role, fio, createdAt string
	err := s.db.QueryRow(
		`SELECT email, role, fio, created_at FROM users WHERE id = ?`, id,
	).Scan(&email, &role, &fio, &createdAt)
	if err != nil {
		return nil, err
	}
	return userFromRow(id, email, role, fio, createdAt), nil
}

func (s *Store) DeleteUser(id int64) error {
	_, err := s.db.Exec(`DELETE FROM users WHERE id = ?`, id)
	return err
}

func (s *Store) GetByEmail(email string) (*User, error) {
	email = normalizeEmail(email)
	var id int64
	var role, fio, createdAt string
	err := s.db.QueryRow(
		`SELECT id, role, fio, created_at FROM users WHERE email = ?`, email,
	).Scan(&id, &role, &fio, &createdAt)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("user not found")
	}
	if err != nil {
		return nil, err
	}
	return userFromRow(id, email, role, fio, createdAt), nil
}

func normalizeEmail(e string) string {
	return strings.ToLower(strings.TrimSpace(e))
}
