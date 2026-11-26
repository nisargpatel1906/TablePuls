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
  display_name?: string | null;
  section_name: string;
  min_capacity?: number;
  seat_capacity: number;
  polygon_json: PolygonPoint[];
  floor_x: number;
  floor_y: number;
  shape: "RECT" | "CIRCLE" | "BOOTH" | string;
  is_active?: boolean;
  is_combinable?: boolean;
  is_monitored?: boolean;
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
  unmonitored_tables?: FloorTable[];
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
  stream_type: "RTSP" | "RTSPS" | "HLS" | "HTTP_MJPEG" | "RTMP" | "DEMO_MP4" | string;
  masked_stream_url?: string;
  target_fps: number;
  face_blur_enabled: boolean;
  status: "ONLINE" | "RECONNECTING" | "OFFLINE" | "DISABLED" | string;
  last_heartbeat_at: string | null;
  exclusion_polygons_json: PolygonPoint[][];
}

// Phase 2 Interfaces (SCR-017 .. SCR-022)
export interface AdminTableItem {
  id: string;
  venue_id: string;
  camera_id: string | null;
  table_code: string;
  display_name: string | null;
  section_name: string;
  min_capacity: number;
  seat_capacity: number;
  shape: "RECT" | "CIRCLE" | "BOOTH" | string;
  is_active: boolean;
  is_combinable: boolean;
  table_notes: string | null;
  floor_x: number;
  floor_y: number;
  polygon_json: PolygonPoint[] | null;
  sort_order: number;
  is_monitored: boolean;
  current_state: TableState;
  current_guest_count: number;
  version: number;
  created_at: string;
  qr_token: string | null;
  qr_url: string | null;
  qr_status: string | null;
  qr_scan_count: number;
}

export interface VenueMenuSettings {
  currency_code: string;
  menu_public_enabled: boolean;
  show_unavailable_items_public: boolean;
  logo_storage_key: string | null;
  logo_url: string | null;
  menu_tagline: string | null;
  menu_revision: number;
  qr_grace_days: number;
  allow_host_menu_availability: boolean;
}

export interface ScheduleWindowDTO {
  days: number[];
  start: string;
  end: string;
}

export interface MenuScheduleDTO {
  v: 1;
  windows: ScheduleWindowDTO[];
}

export interface MenuDTO {
  id: string;
  venue_id: string;
  name: string;
  description: string | null;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED" | string;
  is_active: boolean;
  is_default: boolean;
  schedule_json: MenuScheduleDTO | null;
  sort_order: number;
  category_count: number;
  item_count: number;
}

export interface MenuCategoryDTO {
  id: string;
  venue_id: string;
  menu_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  item_count: number;
}

export interface MenuItemVariantDTO {
  name: string;
  price_minor_units: number;
  is_available: boolean;
}

export interface MenuItemDTO {
  id: string;
  venue_id: string;
  category_id: string;
  name: string;
  description: string | null;
  price_minor_units: number;
  compare_at_price_minor_units: number | null;
  image_asset_id: string | null;
  image_url: string | null;
  thumb_url: string | null;
  image_alt: string | null;
  is_available: boolean;
  unavailable_until: string | null;
  is_featured: boolean;
  dietary_tags: string[];
  allergens: string[];
  variants_json: MenuItemVariantDTO[];
  prep_time_minutes: number | null;
  calories_kcal: number | null;
  sort_order: number;
  version: number;
  updated_at: string;
}

export interface QRCodeItemDTO {
  table_id: string;
  table_code: string;
  table_label: string;
  section_name: string;
  is_active: boolean;
  qr_id: string | null;
  token: string | null;
  qr_url: string | null;
  status: string;
  scan_count: number;
  scans_7d: number;
  last_scanned_at: string | null;
  grace_token_active: boolean;
  grace_until: string | null;
}

export interface PublicMenuItemDTO {
  id: string;
  name: string;
  description: string | null;
  price_minor_units: number;
  compare_at_price_minor_units: number | null;
  image_url: string | null;
  thumb_url: string | null;
  image_alt: string | null;
  is_available: boolean;
  is_featured: boolean;
  dietary_tags: string[];
  allergens: string[];
  variants_json: MenuItemVariantDTO[];
  prep_time_minutes: number | null;
  calories_kcal: number | null;
}

export interface PublicMenuCategoryDTO {
  id: string;
  name: string;
  description: string | null;
  items: PublicMenuItemDTO[];
}

export interface PublicMenuSectionDTO {
  id: string;
  name: string;
  description: string | null;
  categories: PublicMenuCategoryDTO[];
}

export interface PublicMenuPayload {
  venue: {
    name: string;
    tagline: string | null;
    logo_url: string | null;
    currency_code: string;
    timezone: string;
  };
  table: {
    label: string;
  };
  menu_public_enabled: boolean;
  show_unavailable_items: boolean;
  preview_mode: boolean;
  menu_revision: number;
  menus: PublicMenuSectionDTO[];
}
