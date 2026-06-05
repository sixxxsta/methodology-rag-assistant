"use client";

import type { User } from "./types";

const TOKEN_KEY = "methodology_token";
const USER_KEY = "methodology_user";
const CYCLE_KEY = "edagent_cycle_id";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(CYCLE_KEY);
}

export function getCycleId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(CYCLE_KEY);
  if (!raw) return null;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : null;
}

export function setCycleId(id: number) {
  localStorage.setItem(CYCLE_KEY, String(id));
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("edagent-cycle-changed"));
  }
}

export function normalizeRole(role: string | undefined): User["role"] {
  if (role === "admin" || role === "curator" || role === "student") return role;
  if (role === "user") return "curator";
  return "student";
}

export function isAdmin(user: User | null): boolean {
  return user?.role === "admin";
}

export function isCurator(user: User | null): boolean {
  return user?.role === "curator";
}

export function isStudent(user: User | null): boolean {
  return user?.role === "student";
}

export function canUseEdAgent(user: User | null): boolean {
  return user?.role === "admin" || user?.role === "curator";
}

export function roleLabel(role: User["role"]): string {
  switch (role) {
    case "admin":
      return "модерация";
    case "curator":
      return "куратор";
    case "student":
      return "ученик";
  }
}

export function authHeaders(extra?: HeadersInit): HeadersInit {
  const h = new Headers(extra);
  const token = getToken();
  if (token) h.set("Authorization", `Bearer ${token}`);
  const cycleId = getCycleId();
  if (cycleId) h.set("X-Cycle-Id", String(cycleId));
  return h;
}
