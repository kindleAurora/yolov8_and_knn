export interface DeviceSummary {
  id: number;
  farm_id: number;
  code: string;
  name: string;
  device_type: string;
  stream_url: string;
  install_location: string | null;
  status: string;
  is_enabled: boolean;
  last_seen_at: string | null;
  config: Record<string, unknown>;
  zone_count: number;
  updated_at: string;
}

export interface DevicePayload {
  code: string;
  name: string;
  device_type: string;
  stream_url: string;
  install_location: string | null;
  status: string;
  is_enabled: boolean;
  config: Record<string, unknown>;
}
