export type AccountStatus = "pending" | "connected" | "error";

export type ScanStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"
  | "paused";

export type ScanPhase =
  | "enumeration"
  | "topology_mapping"
  | "ha_classification"
  | "cost_analysis"
  | "criticality_inference"
  | "report_generation"
  | "enrichment";

export type PhaseStatus = "pending" | "in_progress" | "completed" | "error";

export type HAClassification =
  | "eligible"
  | "ineligible_builtin"
  | "ineligible_tier1"
  | "partial"
  | "unknown";

export type ConfidenceLevel = "high" | "medium" | "low";

export type CriticalityTier = "tier1" | "tier2" | "tier3" | "unclassified";

export type AuditLogSeverity = "info" | "warning" | "error" | "debug";

export type ConnectionMethod =
  | "cloudformation"
  | "terraform"
  | "manual"
  | "organizations";

export interface CloudAccount {
  id: string;
  aws_account_id: string;
  account_name: string | null;
  iam_role_arn: string;
  external_id: string;
  status: AccountStatus;
  regions_enabled: string[];
  last_scan_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanSession {
  id: string;
  account_id: string;
  status: ScanStatus;
  current_phase: ScanPhase | null;
  resources_found: number;
  multi_az_eligible: number;
  estimated_monthly_savings: number | null;
  total_monthly_cost: number | null;
  eligible_spend: number | null;
  regions_scanned: number;
  errors_count: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface PhaseProgress {
  phase: ScanPhase;
  status: PhaseStatus;
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  details: Record<string, SubTaskProgress>;
}

export interface SubTaskProgress {
  label: string;
  status: PhaseStatus;
  items_found: number;
  duration_seconds: number | null;
}

export interface ScanProgress {
  scan_id: string;
  status: ScanStatus;
  overall_pct: number;
  phases: PhaseProgress[];
  totals: ScanRunningTotals;
  log_entries: AuditLogEntry[];
}

export interface ScanRunningTotals {
  resources_discovered: number;
  multi_az_eligible: number;
  regions_with_resources: number;
  dependencies_mapped: number;
  estimated_savings: number | null;
  zombies_found: number;
}

export interface DiscoveredResource {
  id: string;
  scan_id: string;
  arn: string;
  resource_name: string | null;
  service: string;
  resource_type: string;
  region: string;
  availability_zone: string | null;
  is_multi_az: boolean;
  ha_classification: HAClassification;
  confidence: ConfidenceLevel;
  criticality_tier: CriticalityTier;
  monthly_cost: number | null;
  estimated_savings: number | null;
  savings_pct: number | null;
  configuration: Record<string, unknown>;
  tags: Record<string, string>;
}

export interface ResourceDependency {
  id: string;
  source_resource_id: string;
  target_resource_id: string;
  dependency_type: string;
  confidence: ConfidenceLevel;
}

export interface AuditLogEntry {
  id: string;
  scan_id: string;
  timestamp: string;
  phase: ScanPhase | null;
  service: string | null;
  action: string;
  status: string;
  severity: AuditLogSeverity;
  message: string;
  resource_arn: string | null;
  details: Record<string, unknown> | null;
  duration_ms: number | null;
}

export interface ConnectionTestResult {
  success: boolean;
  checks: ConnectionCheck[];
}

export interface ConnectionCheck {
  service: string;
  status: "success" | "partial" | "failed";
  message: string | null;
}

export interface CreateAccountPayload {
  aws_account_id: string;
  account_name?: string;
  iam_role_arn: string;
  external_id: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScanResourcesParams {
  page?: number;
  page_size?: number;
  service?: string;
  ha_classification?: HAClassification;
  confidence?: ConfidenceLevel;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

export interface ScanLogParams {
  page?: number;
  page_size?: number;
  phase?: ScanPhase;
  service?: string;
  severity?: AuditLogSeverity;
  search?: string;
}
