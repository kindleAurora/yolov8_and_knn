import { apiRequest } from '@/api/http';
import type { AlertRulePayload, AlertRuleSummary } from '@/types/rule';

export function listRules(): Promise<AlertRuleSummary[]> {
  return apiRequest<AlertRuleSummary[]>('/api/v1/rules');
}

export function createRule(payload: AlertRulePayload): Promise<AlertRuleSummary> {
  return apiRequest<AlertRuleSummary>('/api/v1/rules', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateRule(ruleId: number, payload: AlertRulePayload): Promise<AlertRuleSummary> {
  return apiRequest<AlertRuleSummary>(`/api/v1/rules/${ruleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function updateRuleStatus(ruleId: number, isEnabled: boolean): Promise<AlertRuleSummary> {
  return apiRequest<AlertRuleSummary>(`/api/v1/rules/${ruleId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ is_enabled: isEnabled }),
  });
}

export function deleteRule(ruleId: number): Promise<{ id: number }> {
  return apiRequest<{ id: number }>(`/api/v1/rules/${ruleId}`, {
    method: 'DELETE',
  });
}
