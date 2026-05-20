export interface ServiceDependency {
  name: string;
  status: 'up' | 'down' | 'unknown';
  detail: string;
}

export interface HealthPayload {
  service: string;
  environment: string;
  version: string;
  phase: string;
  dependencies: ServiceDependency[];
}
