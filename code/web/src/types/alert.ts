export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export interface AlertSummary {
  id: number;
  farm_id: number;
  rule_id: number | null;
  rule_name: string | null;
  behavior_event_id: number | null;
  device_id: number | null;
  device_name: string | null;
  device_code: string;
  severity: string;
  status: AlertStatus;
  title: string;
  description: string;
  rule_source: string;
  triggered_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  handling_note: string | null;
  handled_by_user_name: string | null;
  snapshot: Record<string, unknown>;
  created_at: string;
}

export interface AlertListResult {
  total: number;
  page: number;
  page_size: number;
  items: AlertSummary[];
}

export interface AlertSummaryStats {
  total_count: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
  high_severity_count: number;
  recent_alerts: AlertSummary[];
}

export interface AlertStatusUpdatePayload {
  status: AlertStatus;
  handling_note?: string | null;
}
