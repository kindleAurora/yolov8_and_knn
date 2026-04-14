import { apiRequest } from '@/api/http';
import type {
  HistoryAnalysisSummary,
  PagedHistoryAlertResult,
  PagedHistoryBehaviorEventResult,
} from '@/types/history';

interface HistoryCommonOptions {
  startAt?: string;
  endAt?: string;
  deviceId?: number;
  page?: number;
  pageSize?: number;
}

interface HistoryBehaviorOptions extends HistoryCommonOptions {
  behaviorType?: string;
}

interface HistoryAlertOptions extends HistoryCommonOptions {
  severity?: string;
  status?: string;
  ruleSource?: string;
}

function applyCommonParams(query: URLSearchParams, options: HistoryCommonOptions) {
  if (options.startAt) {
    query.set('start_at', options.startAt);
  }
  if (options.endAt) {
    query.set('end_at', options.endAt);
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
}

export function listHistoryBehaviorEvents(options: HistoryBehaviorOptions = {}): Promise<PagedHistoryBehaviorEventResult> {
  const query = new URLSearchParams();
  applyCommonParams(query, options);
  if (options.behaviorType) {
    query.set('behavior_type', options.behaviorType);
  }

  const search = query.toString();
  return apiRequest<PagedHistoryBehaviorEventResult>(`/api/v1/history/behavior-events${search ? `?${search}` : ''}`);
}

export function listHistoryAlerts(options: HistoryAlertOptions = {}): Promise<PagedHistoryAlertResult> {
  const query = new URLSearchParams();
  applyCommonParams(query, options);
  if (options.severity) {
    query.set('severity', options.severity);
  }
  if (options.status) {
    query.set('status', options.status);
  }
  if (options.ruleSource) {
    query.set('rule_source', options.ruleSource);
  }

  const search = query.toString();
  return apiRequest<PagedHistoryAlertResult>(`/api/v1/history/alerts${search ? `?${search}` : ''}`);
}

export function fetchHistoryAnalysis(options: Omit<HistoryCommonOptions, 'page' | 'pageSize'> = {}): Promise<HistoryAnalysisSummary> {
  const query = new URLSearchParams();
  applyCommonParams(query, options);
  const search = query.toString();
  return apiRequest<HistoryAnalysisSummary>(`/api/v1/history/analysis${search ? `?${search}` : ''}`);
}
