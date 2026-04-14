import { apiRequest } from '@/api/http';
import type {
  BehaviorEventImportPayload,
  BehaviorEventImportResult,
  BehaviorEventStats,
  BehaviorEventSummary,
  InferenceMeta,
} from '@/types/event';

interface ListBehaviorEventsOptions {
  deviceId?: number;
  behaviorType?: string;
  limit?: number;
}

export function listBehaviorEvents(options: ListBehaviorEventsOptions = {}): Promise<BehaviorEventSummary[]> {
  const query = new URLSearchParams();

  if (options.deviceId) {
    query.set('device_id', String(options.deviceId));
  }
  if (options.behaviorType) {
    query.set('behavior_type', options.behaviorType);
  }
  if (options.limit) {
    query.set('limit', String(options.limit));
  }

  const search = query.toString();
  return apiRequest<BehaviorEventSummary[]>(`/api/v1/events${search ? `?${search}` : ''}`);
}

export function fetchBehaviorEventSummary(deviceId?: number): Promise<BehaviorEventStats> {
  const query = new URLSearchParams();
  if (deviceId) {
    query.set('device_id', String(deviceId));
  }

  const search = query.toString();
  return apiRequest<BehaviorEventStats>(`/api/v1/events/summary${search ? `?${search}` : ''}`);
}

export function fetchInferenceMeta(): Promise<InferenceMeta> {
  return apiRequest<InferenceMeta>('/api/v1/events/inference-meta');
}

export function importBehaviorEvents(payload: BehaviorEventImportPayload): Promise<BehaviorEventImportResult> {
  return apiRequest<BehaviorEventImportResult>('/api/v1/events/import', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
