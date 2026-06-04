'use client';

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
export const TOKEN_KEY = 'leadforge_token';

export function getToken() {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function authHeaders(extra: Record<string, string> = {}) {
  const token = getToken();
  return {
    ...extra,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function authFetch(path: string, options: RequestInit = {}) {
  const headers = authHeaders((options.headers as Record<string, string>) || {});
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && typeof window !== 'undefined') {
    clearToken();
    window.location.href = '/login';
  }

  return res;
}

export function requireAuth() {
  if (typeof window !== 'undefined' && !getToken()) {
    window.location.href = '/login';
    return false;
  }
  return true;
}
