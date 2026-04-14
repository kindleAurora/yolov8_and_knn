export type RuleType = 'lying_duration' | 'zone_dwell' | 'no_drinking';
export type RuleSeverity = 'low' | 'medium' | 'high';

export interface AlertRuleSummary {
  id: number;
  farm_id: number;
  device_id: number | null;
  device_name: string | null;
  name: string;
  description: string | null;
  rule_type: RuleType;
  severity: RuleSeverity;
  source: string;
  threshold_minutes: number;
  zone_name: string | null;
  behavior_type: string | null;
  is_enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AlertRulePayload {
  name: string;
  description?: string | null;
  rule_type: RuleType;
  severity: RuleSeverity;
  threshold_minutes: number;
  device_id?: number | null;
  zone_name?: string | null;
  behavior_type?: string | null;
  is_enabled: boolean;
  config: Record<string, unknown>;
}
