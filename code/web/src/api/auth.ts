import { apiRequest } from '@/api/http';
import type { CurrentUser, LoginPayload } from '@/types/auth';

export function login(username: string, password: string): Promise<LoginPayload> {
  return apiRequest<LoginPayload>('/api/v1/auth/login', {
    method: 'POST',
    auth: false,
    body: JSON.stringify({ username, password }),
  });
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return apiRequest<CurrentUser>('/api/v1/auth/me');
}

export function logout(): Promise<{ logged_out: boolean }> {
  return apiRequest<{ logged_out: boolean }>('/api/v1/auth/logout', {
    method: 'POST',
  });
}
