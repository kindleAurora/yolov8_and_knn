export interface HistoryBehaviorEventItem {
  id: number;
  device_id: number | null;
  device_name: string | null;
  device_code: string;
  zone_name: string | null;
  behavior_type: string;
  cow_count: number;
  confidence: number;
  occurred_at: string;
  source_type: string;
  model_name: string;
}

export interface HistoryAlertItem {
  id: number;
  rule_id: number | null;
  rule_name: string | null;
  device_id: number | null;
  device_name: string | null;
  device_code: string;
  severity: string;
  status: string;
  title: string;
  rule_source: string;
  triggered_at: string;
  handling_note: string | null;
}

export interface PagedHistoryBehaviorEventResult {
  total: number;
  page: number;
  page_size: number;
  items: HistoryBehaviorEventItem[];
}

export interface PagedHistoryAlertResult {
  total: number;
  page: number;
  page_size: number;
  items: HistoryAlertItem[];
}

export interface HistoryTrendPoint {
  label: string;
  value: number;
}

export interface HistorySharePoint {
  label: string;
  value: number;
  share: number;
}

export interface HistoryAnalysisSummary {
  window_start: string;
  window_end: string;
  total_behavior_events: number;
  total_alerts: number;
  behavior_trend: HistoryTrendPoint[];
  alert_trend: HistoryTrendPoint[];
  behavior_share: HistorySharePoint[];
  alert_severity_distribution: HistorySharePoint[];
}
