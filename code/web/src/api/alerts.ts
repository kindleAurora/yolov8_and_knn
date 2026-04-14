import { apiRequest } from '@/api/http';
import type { AlertListResult, AlertStatusUpdatePayload, AlertSummary, AlertSummaryStats } from '@/types/alert';

interface ListAlertsOptions {
  status?: string;
  severity?: string;
  ruleSource?: string;
  deviceId?: number;
  page?: number;
  pageSize?: number;
}

export function listAlerts(options: ListAlertsOptions = {}): Promise<AlertListResult> {
  const query = new URLSearchParams();

  if (options.status) {
    query.set('status', options.status);
  }
  if (options.severity) {
    query.set('severity', options.severity);
  }
  if (options.ruleSource) {
    query.set('rule_source', options.ruleSource);
  }
  if (options.deviceId) {
    query.set('device_id', String(options.deviceId));
  }
  if (options.page) {
    query.set('page', String(options.page));
  }
  if (options.pageSize) {
    query.set('page_size', String(options.pageSize));
  }

  const search = query.toString();
  return apiRequest<AlertListResult>(`/api/v1/alerts${search ? `?${search}` : ''}`);
}

export function fetchAlertSummary(): Promise<AlertSummaryStats> {
  return apiRequest<AlertSummaryStats>('/api/v1/alerts/summary');
}

export function getAlert(alertId: number): Promise<AlertSummary> {
  return apiRequest<AlertSummary>(`/api/v1/alerts/${alertId}`);
}

export function updateAlertStatus(alertId: number, payload: AlertStatusUpdatePayload): Promise<AlertSummary> {
  return apiRequest<AlertSummary>(`/api/v1/alerts/${alertId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
