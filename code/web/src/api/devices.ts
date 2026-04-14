import { apiRequest } from '@/api/http';
import type { DevicePayload, DeviceSummary } from '@/types/device';

export function listDevices(includeDisabled = true): Promise<DeviceSummary[]> {
  const query = includeDisabled ? '?include_disabled=true' : '?include_disabled=false';
  return apiRequest<DeviceSummary[]>(`/api/v1/devices${query}`);
}

export function getDevice(deviceId: number): Promise<DeviceSummary> {
  return apiRequest<DeviceSummary>(`/api/v1/devices/${deviceId}`);
}

export function createDevice(payload: DevicePayload): Promise<DeviceSummary> {
  return apiRequest<DeviceSummary>('/api/v1/devices', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateDevice(deviceId: number, payload: DevicePayload): Promise<DeviceSummary> {
  return apiRequest<DeviceSummary>(`/api/v1/devices/${deviceId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function updateDeviceStatus(
  deviceId: number,
  payload: Pick<DevicePayload, 'status' | 'is_enabled'>,
): Promise<DeviceSummary> {
  return apiRequest<DeviceSummary>(`/api/v1/devices/${deviceId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteDevice(deviceId: number): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/api/v1/devices/${deviceId}`, {
    method: 'DELETE',
  });
}
