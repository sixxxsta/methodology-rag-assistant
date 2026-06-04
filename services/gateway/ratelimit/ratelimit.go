package ratelimit

import (
	"net/http"
	"sync"
	"time"
)

type limiter struct {
	mu       sync.Mutex
	count    int
	window   time.Time
	max      int
	interval time.Duration
}

func newLimiter(max int, interval time.Duration) *limiter {
	return &limiter{max: max, interval: interval, window: time.Now()}
}

func (l *limiter) allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	if now.Sub(l.window) >= l.interval {
		l.window = now
		l.count = 0
	}
	if l.count >= l.max {
		return false
	}
	l.count++
	return true
}

type Middleware struct {
	limits map[string]*limiter
}

func New(registerPerMin, chatPerMin int) *Middleware {
	if registerPerMin <= 0 {
		registerPerMin = 10
	}
	if chatPerMin <= 0 {
		chatPerMin = 30
	}
	return &Middleware{
		limits: map[string]*limiter{
			"POST /api/auth/register": newLimiter(registerPerMin, time.Minute),
			"POST /api/chat":          newLimiter(chatPerMin, time.Minute),
		},
	}
}

func (m *Middleware) Wrap(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := r.Method + " " + r.URL.Path
		if lim, ok := m.limits[key]; ok && !lim.allow() {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusTooManyRequests)
			_, _ = w.Write([]byte(`{"error":"rate limit exceeded"}`))
			return
		}
		next.ServeHTTP(w, r)
	})
}
