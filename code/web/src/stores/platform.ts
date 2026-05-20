import { defineStore } from 'pinia';

import { fetchPlatformHealth } from '@/api/platform';
import type { HealthPayload } from '@/types/health';

type LoadState = 'idle' | 'loading' | 'success' | 'error';

export const usePlatformStore = defineStore('platform', {
  state: () => ({
    health: null as HealthPayload | null,
    loadState: 'idle' as LoadState,
    errorMessage: '',
  }),
  actions: {
    async loadHealth() {
      this.loadState = 'loading';
      this.errorMessage = '';

      try {
        this.health = await fetchPlatformHealth();
        this.loadState = 'success';
      } catch (error) {
        this.loadState = 'error';
        this.errorMessage = error instanceof Error ? error.message : '无法加载平台健康状态。';
      }
    },
  },
});
