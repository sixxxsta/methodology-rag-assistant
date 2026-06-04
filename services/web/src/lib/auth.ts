"use client";

import type { User } from "./types";

const TOKEN_KEY = "methodology_token";
const USER_KEY = "methodology_user";

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
  return h;
}
