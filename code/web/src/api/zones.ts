import { apiRequest } from '@/api/http';
import type { ZonePayload, ZoneSummary } from '@/types/zone';

export function listZones(deviceId?: number): Promise<ZoneSummary[]> {
  const query = deviceId ? `?device_id=${deviceId}` : '';
  return apiRequest<ZoneSummary[]>(`/api/v1/zones${query}`);
}

export function createZone(payload: ZonePayload): Promise<ZoneSummary> {
  return apiRequest<ZoneSummary>('/api/v1/zones', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateZone(zoneId: number, payload: ZonePayload): Promise<ZoneSummary> {
  return apiRequest<ZoneSummary>(`/api/v1/zones/${zoneId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function deleteZone(zoneId: number): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/v1/zones/${zoneId}`, {
    method: 'DELETE',
  });
}
