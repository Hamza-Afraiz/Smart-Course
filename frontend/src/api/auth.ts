import { api } from "./client";
import type { Role, TokenResponse, User } from "./types";

// Login uses the OAuth2 password flow — form-encoded body, not JSON.
export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const { data } = await api.post<TokenResponse>("/auth/login", body, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data.access_token;
}

export async function register(payload: {
  email: string;
  password: string;
  full_name?: string;
  role: Role;
}): Promise<User> {
  const { data } = await api.post<User>("/auth/register", payload);
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>("/users/me");
  return data;
}

export async function updateMe(payload: {
  full_name?: string;
  password?: string;
}): Promise<User> {
  const { data } = await api.patch<User>("/users/me", payload);
  return data;
}
