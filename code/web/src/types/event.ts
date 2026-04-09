export type EventSourceType = 'image' | 'video' | 'stream' | 'edge-report';
export type InferenceMode = 'yolo-knn' | 'yolo-only';

export interface InferenceModelOption {
  key: string;
  label: string;
  path: string;
  is_default: boolean;
}

export interface InferenceMeta {
  service: string;
  service_mode: string;
  supported_sources: EventSourceType[];
  available_inference_modes: InferenceMode[];
  default_inference_mode: InferenceMode;
  default_yolo_model_key: string | null;
  default_yolo_confidence: number;
  default_yolo_iou: number;
  default_knn_confidence_threshold: number;
  available_yolo_models: InferenceModelOption[];
  knn_model_loaded: boolean;
}

export interface BehaviorEventSummary {
  id: number;
  request_id: string;
  farm_id: number;
  device_id: number | null;
  device_code: string;
  device_name: string | null;
  zone_id: number | null;
  zone_name: string | null;
  behavior_type: string;
  cow_count: number;
  confidence: number;
  occurred_at: string;
  model_name: string;
  model_version: string;
  inference_source: string;
  source_type: EventSourceType;
  source_uri: string;
  frame_uri: string | null;
  notes: string | null;
  media_asset_id: number | null;
  media_asset_uri: string | null;
  created_at: string;
}

export interface BehaviorEventImportPayload {
  request_id?: string | null;
  device_code: string;
  source_type: EventSourceType;
  source_uri: string;
  occurred_at: string;
  frame_uri?: string | null;
  inference_mode: InferenceMode;
  yolo_model_key?: string | null;
  metadata: Record<string, unknown>;
}

export interface BehaviorEventImportResult {
  request_id: string;
  imported_count: number;
  model_name: string;
  model_version: string;
  inference_source: string;
  media_asset_id: number | null;
  behavior_events: BehaviorEventSummary[];
}

export interface BehaviorEventStats {
  total_count: number;
  today_count: number;
  recent_events: BehaviorEventSummary[];
}
