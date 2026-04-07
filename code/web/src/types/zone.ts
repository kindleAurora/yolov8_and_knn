export interface ZonePoint {
  x: number;
  y: number;
}

export interface ZoneSummary {
  id: number;
  farm_id: number;
  device_id: number;
  name: string;
  zone_type: string;
  shape_type: string;
  points: ZonePoint[];
  is_enabled: boolean;
  updated_at: string;
}

export interface ZonePayload {
  device_id: number;
  name: string;
  zone_type: string;
  shape_type: string;
  points: ZonePoint[];
  is_enabled: boolean;
}
