import { apiRequest } from '@/api/http';
import type { HealthPayload } from '@/types/health';

export function fetchPlatformHealth(): Promise<HealthPayload> {
  return apiRequest<HealthPayload>('/health', { auth: false });
}
