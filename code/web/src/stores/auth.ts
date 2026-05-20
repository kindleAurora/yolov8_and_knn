import { defineStore } from 'pinia';

import { fetchCurrentUser, login as loginRequest, logout as logoutRequest } from '@/api/auth';
import type { CurrentUser } from '@/types/auth';
import { clearStoredSession, getStoredToken, getStoredUser, persistSession } from '@/utils/session';

type AuthState = 'idle' | 'loading' | 'authenticated' | 'anonymous';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: null as string | null,
    currentUser: null as CurrentUser | null,
    authState: 'idle' as AuthState,
    initialized: false,
    errorMessage: '',
    initializePromise: null as Promise<void> | null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.currentUser),
    isAdmin: (state) => Boolean(state.currentUser?.roles.includes('admin')),
  },
  actions: {
    hydrate() {
      this.token = getStoredToken();
      this.currentUser = getStoredUser();
      this.authState = this.token && this.currentUser ? 'authenticated' : 'anonymous';
    },
    clearSession() {
      this.token = null;
      this.currentUser = null;
      this.authState = 'anonymous';
      this.errorMessage = '';
      clearStoredSession();
    },
    async initialize() {
      if (this.initialized) {
        return;
      }
      if (this.initializePromise) {
        return this.initializePromise;
      }

      this.initializePromise = (async () => {
        this.hydrate();
        if (!this.token) {
          this.initialized = true;
          this.authState = 'anonymous';
          return;
        }

        try {
          this.currentUser = await fetchCurrentUser();
          if (this.currentUser) {
            persistSession(this.token, this.currentUser);
            this.authState = 'authenticated';
          } else {
            this.clearSession();
          }
        } catch {
          this.clearSession();
        } finally {
          this.initialized = true;
          this.initializePromise = null;
        }
      })();

      return this.initializePromise;
    },
    async login(username: string, password: string) {
      this.authState = 'loading';
      this.errorMessage = '';

      try {
        const payload = await loginRequest(username, password);
        this.token = payload.access_token;
        this.currentUser = payload.user;
        this.authState = 'authenticated';
        this.initialized = true;
        persistSession(payload.access_token, payload.user);
        return payload.user;
      } catch (error) {
        this.authState = 'anonymous';
        this.errorMessage = error instanceof Error ? error.message : '登录失败。';
        throw error;
      }
    },
    async logout() {
      try {
        if (this.token) {
          await logoutRequest();
        }
      } catch {
        // Ignore network errors during client-side logout.
      } finally {
        this.clearSession();
      }
    },
  },
});
