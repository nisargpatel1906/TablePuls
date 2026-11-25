import type { TableState } from "@/lib/table-states";

export interface PolygonPoint {
  x: number;
  y: number;
}

export interface FloorTable {
  id: string;
  venue_id: string;
  camera_id: string | null;
  table_code: string;
  section_name: string;
  seat_capacity: number;
  polygon_json: PolygonPoint[];
  floor_x: number;
  floor_y: number;
  shape: "RECT" | "CIRCLE" | "BOOTH" | string;
  current_state: TableState;
  current_guest_count: number;
  current_confidence: number | null;
  occupied_since: string | null;
  last_staff_visit_at: string | null;
  predicted_free_at: string | null;
  version: number;
}

export interface FloorSnapshot {
  venue_id: string;
  kpis: {
    occupied_tables: number;
    total_tables: number;
    seated_guests: number;
    total_seats: number;
    capacity_pct: number;
    active_alerts: number;
  };
  ai_inference_enabled: boolean;
  cameras_summary: {
    total: number;
    online: number;
    offline: number;
  };
  tables: FloorTable[];
}

export interface TableEventItem {
  id: string;
  previous_state: TableState;
  new_state: TableState;
  guest_count: number;
  confidence: number | null;
  source: "AI" | "MANUAL" | "SYSTEM" | string;
  reason: string | null;
  occurred_at: string;
}

export interface TableDetailData {
  table: FloorTable;
  latest_snapshot_available: boolean;
  events: TableEventItem[];
}

export interface AlertItem {
  id: string;
  venue_id: string;
  table_id: string | null;
  table_code: string | null;
  camera_id: string | null;
  alert_type: string;
  severity: string;
  status: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED" | string;
  message: string;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export interface WaitlistItem {
  id: string;
  venue_id: string;
  party_name: string;
  party_size: number;
  has_phone: boolean;
  quoted_wait_minutes: number | null;
  status: "WAITING" | "SEATED" | "CANCELLED" | "NO_SHOW" | string;
  assigned_table_id: string | null;
  notes: string | null;
  elapsed_wait_minutes: number;
  actual_wait_minutes: number | null;
  joined_at: string;
  seated_at: string | null;
}

export interface TurnoverPredictionItem {
  table_id: string;
  table_code: string;
  section_name: string;
  seat_capacity: number;
  current_state: TableState;
  elapsed_dwell_minutes: number;
  eta_min_minutes: number;
  eta_max_minutes: number;
  eta_display: string;
  confidence_tier: string;
}

export interface CameraItem {
  id: string;
  venue_id: string;
  name: string;
  stream_type: "RTSP" | "RTSPS" | "DEMO_MP4" | string;
  masked_stream_url?: string;
  target_fps: number;
  face_blur_enabled: boolean;
  status: "ONLINE" | "RECONNECTING" | "OFFLINE" | "DISABLED" | string;
  last_heartbeat_at: string | null;
  exclusion_polygons_json: PolygonPoint[][];
}
