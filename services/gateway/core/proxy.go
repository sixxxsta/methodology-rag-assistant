package core

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"methodology-rag-assistant/auth"
)

type Proxy struct {
	proxy          *httputil.ReverseProxy
	internalSecret string
}

func NewProxy(baseURL, internalSecret string) (*Proxy, error) {
	target, err := url.Parse(strings.TrimRight(baseURL, "/"))
	if err != nil {
		return nil, err
	}
	rp := httputil.NewSingleHostReverseProxy(target)
	rp.Transport = &http.Transport{
		ResponseHeaderTimeout: 5 * time.Minute,
		IdleConnTimeout:       90 * time.Second,
	}
	originalDirector := rp.Director
	rp.Director = func(req *http.Request) {
		originalDirector(req)
		req.Host = target.Host
	}
	return &Proxy{proxy: rp, internalSecret: internalSecret}, nil
}

func (p *Proxy) PublicHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if p.internalSecret != "" {
			r.Header.Set("X-Core-Internal-Key", p.internalSecret)
		}
		p.proxy.ServeHTTP(w, r)
	})
}

func (p *Proxy) Handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, ok := auth.ClaimsFromContext(r.Context())
		if !ok {
			http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
			return
		}

		path := strings.TrimPrefix(r.URL.Path, "/api/ed")
		if path == "" {
			path = "/"
		}
		r.URL.Path = "/api" + path

		r.Header.Set("X-User-Email", claims.Email)
		r.Header.Set("X-User-Id", strings.TrimSpace(claims.Subject))
		r.Header.Set("X-User-Role", claims.Role)
		if p.internalSecret != "" {
			r.Header.Set("X-Core-Internal-Key", p.internalSecret)
		}
		if cid := r.Header.Get("X-Correlation-Id"); cid != "" {
			r.Header.Set("X-Correlation-Id", cid)
		}

		p.proxy.ServeHTTP(w, r)
	})
}
