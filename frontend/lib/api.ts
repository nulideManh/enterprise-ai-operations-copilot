export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type UserContext = {
  email: string;
  role: string;
  department: string;
};

export async function apiFetch<T>(
  path: string,
  user: UserContext,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-User-Email", user.email);
  headers.set("X-User-Role", user.role);
  headers.set("X-User-Department", user.department);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}
