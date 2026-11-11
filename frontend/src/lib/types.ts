/**
 * Typed mirrors of the backend Phase 1–4 API response models.
 * Source: backend/app/schemas/*.py
 * Keep these in sync with the backend OpenAPI contract.
 */

export type Role = "admin" | "unit_manager";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  is_active?: boolean;
  must_change_password: boolean;
  created_at?: string;
}

/** The `user` sub-object returned by /auth/login (subset of AuthUser). */
export interface LoginUser {
  id: number;
  email: string;
  full_name: string;
  must_change_password: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: LoginUser;
}

export interface MeResponse extends AuthUser {
  memberships?: { id: number; role: Role; organization_id: number }[];
}

// ---------------- Phase 2 ----------------

export type PlanningCycleStatus =
  | "draft"
  | "open"
  | "submitted"
  | "reviewed"
  | "published";

export interface PlanningCycle {
  id: number;
  name: string;
  term: string | null;
  status: PlanningCycleStatus;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
  deleted_at: string | null;
}

export interface Unit {
  id: number;
  name: string;
  code: string | null;
}

export interface CycleUnit {
  id: number;
  cycle_id: number;
  unit_id: number;
  responsible_user_id: number | null;
}

export type ResourceKind = "room" | "instructor";

export interface Resource {
  id: number;
  kind: ResourceKind;
  name: string;
  code: string | null;
  capacity: number | null;
  details: string | null;
  created_at: string;
}

export interface ResourceAvailability {
  id: number;
  resource_id: number;
  cycle_id: number;
  weekday: number; // 0=شنبه … 6=جمعه
  start_hhmm: string;
  end_hhmm: string;
  reason: string | null;
  deleted_at: string | null;
}

export interface ResourceCommitment {
  id: number;
  resource_id: number;
  cycle_id: number;
  weekday: number;
  start_hhmm: string;
  end_hhmm: string;
  reason: string | null;
}

export interface Cohort {
  id: number;
  name: string;
  entry_year: number | null;
  unit_id: number;
}

export interface CycleCohort {
  id: number;
  cycle_id: number;
  cohort_id: number;
  expected_enrollment: number;
}

export interface Course {
  id: number;
  code: string;
  title: string;
}

export interface CourseOffering {
  id: number;
  course_id: number;
  planning_cycle_id: number;
  section: string | null;
  meetings_per_week: number;
  duration_minutes: number;
  required_room_capacity: number | null;
  room_type: string | null;
  created_at: string;
}

export interface OfferingUnit {
  id: number;
  offering_id: number;
  unit_id: number;
  expected_enrollment: number;
  room_resource_id: number | null;
  instructor_resource_id: number | null;
}

export interface OfferingCohort {
  id: number;
  offering_id: number;
  cohort_id: number;
  expected_enrollment: number;
}

export interface MeetingRequirement {
  id: number;
  offering_id: number;
  allowed_weekday_min: number | null;
  allowed_weekday_max: number | null;
  start_window_hhmm: string | null;
  end_window_hhmm: string | null;
}


// ---------------- Phase 3 ----------------

export type SubmissionStatus =
  | "draft"
  | "submitted"
  | "needs_changes"
  | "approved"
  | "rejected";

export interface Submission {
  id: number;
  cycle_id: number;
  unit_id: number;
  organization_id: number;
  status: SubmissionStatus;
  version: number;
  locked: boolean;
}

export interface SubmissionRevision {
  id: number;
  submission_id: number;
  revision_no: number;
  input_snapshot: Record<string, unknown> | null;
  created_by_user_id: number | null;
}

export interface WizardDraft {
  id: number;
  cycle_id: number;
  unit_id: number;
  section_state: Record<string, unknown>;
  completed: boolean;
}

export interface SharedOfferingApproval {
  id: number;
  offering_id: number;
  unit_id: number;
  status: "unit_approved" | "needs_changes" | "pending";
  comment: string | null;
  decided_by_user_id: number | null;
}

export interface PreflightBlocker {
  code: string;
  message: string;
  subject_type: string | null;
  subject_id: number | null;
}

export interface PreflightResult {
  can_submit: boolean;
  blockers: PreflightBlocker[];
  warnings: PreflightBlocker[];
}

export interface CommentItem {
  id: number;
  submission_id: number;
  revision_no: number | null;
  actor_user_id: number | null;
  text: string;
  created_at: string | null;
}

export interface DomainAuditEvent {
  id: number;
  action: string;
  organization_id: number | null;
  actor_user_id: number | null;
  subject_type: string | null;
  subject_id: number | null;
  detail: Record<string, unknown> | null;
  created_at: string | null;
}

// ---------------- Phase 4 ----------------

export type SolverStatus =
  | "data_gaps"
  | "INFEASIBLE"
  | "FEASIBLE"
  | "FAILED"
  | "running";

export interface SolveResult {
  run_id: number;
  cycle_id: number;
  status: SolverStatus;
  objective_score: number | null;
  stale: boolean;
  can_publish: boolean;
  blockers: PreflightBlocker[];
  warnings: PreflightBlocker[];
  infeasible_causes: Record<string, unknown>[];
}

export interface SolverRun {
  id: number;
  cycle_id: number;
  organization_id: number;
  status: SolverStatus;
  actor_user_id: number | null;
  objective_score: number | null;
  stale: boolean;
  stale_reason: string | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface SolverAssignment {
  id: number;
  run_id: number;
  offering_id: number;
  resource_id: number | null;
  occurrence_no: number;
  weekday: number | null;
  start_hhmm: string | null;
  end_hhmm: string | null;
  meetings_per_week: number | null;
  duration_minutes: number | null;
}

export interface RunDetail {
  run: SolverRun;
  input_snapshot: Record<string, unknown> | null;
  result_snapshot: Record<string, unknown> | null;
  assignments: SolverAssignment[];
}

export interface RunCompareSide {
  run_id: number;
  status: SolverStatus;
  objective_score: number | null;
  stale: boolean;
}

export interface RunComparison {
  a: RunCompareSide;
  b: RunCompareSide;
  shared_offering_changes: Record<string, unknown>[];
  schedule_changes: Record<string, unknown>[];
  score_delta: number | null;
  unresolved_warnings: Record<string, unknown>[];
}

export interface Correction {
  id: number;
  offering_id: number;
  cycle_id: number;
  organization_id: number;
  field: string;
  before_value: string | null;
  after_value: string | null;
  reason: string;
  actor_user_id: number | null;
  approvals_marked_stale: boolean;
  created_at: string;
}

// ---------------- Phase 6: export / publish ----------------

export type PublishedStatus = "draft" | "current" | "previous" | "stale";

export interface PublishedSchedule {
  id: number;
  run_id: number;
  cycle_id: number;
  organization_id: number;
  version: number;
  status: PublishedStatus;
  stale: boolean;
  stale_reason: string | null;
  actor_user_id: number | null;
  input_snapshot: Record<string, unknown> | null;
  result_snapshot: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** Phase 6 export readiness (derived; the API does not return this directly). */
export interface ExportReadiness {
  can_export: boolean;
  reason?: string | null;
}
