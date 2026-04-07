import { apiBlob } from '@/api/http';

export function fetchDevicePreview(deviceId: number): Promise<Blob> {
  return apiBlob(`/api/v1/media/devices/${deviceId}/preview`);
}

export function fetchEventPreview(eventId: number): Promise<Blob> {
  return apiBlob(`/api/v1/media/events/${eventId}/preview`);
}

export function fetchEventSourceMedia(eventId: number): Promise<Blob> {
  return apiBlob(`/api/v1/media/events/${eventId}/source`);
}
