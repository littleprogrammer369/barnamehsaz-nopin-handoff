/**
 * Typed endpoint client. One module per backend router phase so pages stay
 * thin. All calls go through `api()` in ./api which attaches the in-memory
 * bearer token and (same-origin) Vite-proxy prefix.
 */
import { api, API_BASE, store, ApiError } from "./api";
import type {
  PlanningCycle, PlanningCycleStatus,
  Unit, CycleUnit, Resource, ResourceAvailability, ResourceCommitment,
  Cohort, CycleCohort, Course, CourseOffering, OfferingUnit, OfferingCohort,
  MeetingRequirement, Submission, SubmissionRevision, WizardDraft,
  SharedOfferingApproval, PreflightResult, CommentItem, DomainAuditEvent,
  SolveResult, SolverRun, RunDetail, RunComparison, Correction,
} from "./types";

// ---------------- Phase 2: cycles / units / resources / offerings --------
export const Cycles = {
  list: () => api<PlanningCycle[]>("/phase2/planning-cycles"),
  get: (id: number) => api<PlanningCycle>(`/phase2/planning-cycles/${id}`),
  create: (body: { name: string; term?: string; status?: PlanningCycleStatus }) =>
    api<PlanningCycle>("/phase2/planning-cycles", { method: "POST", body }),
  update: (id: number, body: Partial<{ name: string; term: string; status: PlanningCycleStatus }>) =>
    api<PlanningCycle>(`/phase2/planning-cycles/${id}`, { method: "PUT", body }),
  delete: (id: number) =>
    api<void>(`/phase2/planning-cycles/${id}`, { method: "DELETE" }),
};

export const Units = {
  list: () => api<Unit[]>("/phase2/units"),
  create: (body: { name: string; code?: string | null }) =>
    api<Unit>("/phase2/units", { method: "POST", body }),
};

export const CycleUnits = {
  list: (cycleId: number) =>
    api<CycleUnit[]>(`/phase2/planning-cycles/${cycleId}/units`),
  add: (cycleId: number, body: { unit_id: number; responsible_user_id?: number | null }) =>
    api<CycleUnit>(`/phase2/planning-cycles/${cycleId}/units`, { method: "POST", body }),
};

export const Resources = {
  list: (kind?: string) =>
    api<Resource[]>("/phase2/resources", { query: kind ? { kind } : undefined }),
  create: (body: {
    kind: "room" | "instructor";
    name: string;
    code?: string | null;
    capacity?: number | null;
    details?: string | null;
  }) => api<Resource>("/phase2/resources", { method: "POST", body }),
};

export const ResourceAvailabilityClient = {
  list: (resourceId: number, cycleId?: number) =>
    api<ResourceAvailability[]>(
      `/phase2/resources/${resourceId}/availability`,
      { query: cycleId ? { cycle_id: cycleId } : undefined },
    ),
  create: (resourceId: number, body: {
    cycle_id: number;
    weekday: number;
    start_hhmm: string;
    end_hhmm: string;
    reason?: string | null;
  }) =>
    api<ResourceAvailability>(
      `/phase2/resources/${resourceId}/availability`,
      { method: "POST", body },
    ),
  delete: (availabilityId: number) =>
    api<void>(`/phase2/resource-availability/${availabilityId}`, { method: "DELETE" }),
};

export const ResourceCommitments = {
  list: (resourceId: number, cycleId?: number) =>
    api<ResourceCommitment[]>(
      `/phase2/resources/${resourceId}/commitments`,
      { query: cycleId ? { cycle_id: cycleId } : undefined },
    ),
  create: (resourceId: number, body: {
    cycle_id: number;
    weekday: number;
    start_hhmm: string;
    end_hhmm: string;
    reason?: string | null;
  }) =>
    api<ResourceCommitment>(
      `/phase2/resources/${resourceId}/commitments`,
      { method: "POST", body },
    ),
};

export const Cohorts = {
  list: () => api<Cohort[]>("/phase2/cohorts"),
  create: (body: { name: string; entry_year?: number | null; unit_id: number }) =>
    api<Cohort>("/phase2/cohorts", { method: "POST", body }),
};

export const CycleCohorts = {
  list: (cycleId: number) =>
    api<CycleCohort[]>(`/phase2/planning-cycles/${cycleId}/cohorts`),
  add: (cycleId: number, body: { cohort_id: number; expected_enrollment: number }) =>
    api<CycleCohort>(`/phase2/planning-cycles/${cycleId}/cohorts`, { method: "POST", body }),
};

export const Courses = {
  list: () => api<Course[]>("/phase2/courses"),
  create: (body: { code: string; title: string }) =>
    api<Course>("/phase2/courses", { method: "POST", body }),
};

export const Offerings = {
  list: (cycleId?: number) =>
    api<CourseOffering[]>("/phase2/offerings", {
      query: cycleId ? { planning_cycle_id: cycleId } : undefined,
    }),
  get: (id: number) => api<CourseOffering>(`/phase2/offerings/${id}`),
  create: (body: {
    course_id: number;
    planning_cycle_id: number;
    section?: string | null;
    meetings_per_week?: number;
    duration_minutes?: number;
    required_room_capacity?: number | null;
    room_type?: string | null;
  }) => api<CourseOffering>("/phase2/offerings", { method: "POST", body }),
};

export const OfferingUnits = {
  list: (offeringId: number) =>
    api<OfferingUnit[]>(`/phase2/offerings/${offeringId}/units`),
  add: (offeringId: number, body: { unit_id: number; expected_enrollment: number }) =>
    api<OfferingUnit>(`/phase2/offerings/${offeringId}/units`, { method: "POST", body }),
};

export const OfferingCohorts = {
  list: (offeringId: number) =>
    api<OfferingCohort[]>(`/phase2/offerings/${offeringId}/cohorts`),
  add: (offeringId: number, body: { cohort_id: number; expected_enrollment: number }) =>
    api<OfferingCohort>(`/phase2/offerings/${offeringId}/cohorts`, { method: "POST", body }),
};

export const MeetingRequirements = {
  create: (body: {
    offering_id: number;
    allowed_weekday_min?: number | null;
    allowed_weekday_max?: number | null;
    start_window_hhmm?: string | null;
    end_window_hhmm?: string | null;
  }) =>
    api<MeetingRequirement>("/phase2/meeting-requirements", { method: "POST", body }),
  get: (id: number) =>
    api<MeetingRequirement>(`/phase2/meeting-requirements/${id}`),
};

// ---------------- Phase 3: submissions / wizard / shared / preflight ----
export const Submissions = {
  list: (cycleId?: number, unitId?: number) =>
    api<Submission[]>("/phase3/submissions", {
      query: { cycle_id: cycleId, unit_id: unitId },
    }),
  get: (id: number) => api<Submission>(`/phase3/submissions/${id}`),
  create: (body: { cycle_id: number; unit_id: number; input_snapshot?: Record<string, unknown> | null }) =>
    api<Submission>("/phase3/submissions", { method: "POST", body }),
  submit: (id: number, body: { expected_version: number; input_snapshot?: Record<string, unknown> | null }) =>
    api<Submission>(`/phase3/submissions/${id}/submit`, { method: "POST", body }),
  needsChanges: (id: number, body: { reason: string; comment?: string | null; expected_version?: number }) =>
    api<Submission>(`/phase3/submissions/${id}/needs-changes`, { method: "POST", body }),
  approve: (id: number, body: { comment?: string | null; expected_version?: number }) =>
    api<Submission>(`/phase3/submissions/${id}/approve`, { method: "POST", body }),
  revisions: (id: number) =>
    api<SubmissionRevision[]>(`/phase3/submissions/${id}/revisions`),
  addComment: (id: number, body: {
    text: string;
    target?: "submission" | "revision";
    revision_no?: number | null;
  }) => api<CommentItem>(`/phase3/submissions/${id}/comments`, { method: "POST", body }),
  listComments: (id: number) =>
    api<CommentItem[]>(`/phase3/submissions/${id}/comments`),
};

export const Wizard = {
  upsert: (body: { cycle_id: number; unit_id: number; section_state?: Record<string, unknown> | null; completed?: boolean | null }) =>
    api<WizardDraft>("/phase3/wizard-state", { method: "POST", body }),
  get: (cycleId: number, unitId: number) =>
    api<WizardDraft | null>("/phase3/wizard-state", {
      query: { cycle_id: cycleId, unit_id: unitId },
    }),
};

export const SharedOfferings = {
  listApprovals: (offeringId: number) =>
    api<SharedOfferingApproval[]>(`/phase3/offerings/${offeringId}/shared-approvals`),
  record: (offeringId: number, body: { status: "unit_approved" | "needs_changes"; unit_id: number; comment?: string | null }) =>
    api<SharedOfferingApproval>(
      `/phase3/offerings/${offeringId}/shared-approvals`,
      { method: "POST", body },
    ),
  finalize: (offeringId: number, body: { decision: "approve" | "return"; reason?: string | null }) =>
    api<{ offering_id: number; outcome: string; re_pend_approvals: boolean }>(
      `/phase3/offerings/${offeringId}/shared-finalize`,
      { method: "POST", body },
    ),
};

export const Preflight = {
  run: (cycleId?: number) =>
    api<PreflightResult>("/phase3/preflight", {
      query: cycleId ? { cycle_id: cycleId } : undefined,
    }),
};

export const Audit = {
  list: (opts: { subject_type?: string; subject_id?: number; limit?: number } = {}) =>
    api<DomainAuditEvent[]>("/phase3/audit-events", {
      query: {
        subject_type: opts.subject_type,
        subject_id: opts.subject_id,
        limit: opts.limit,
      },
    }),
};

// ---------------- Phase 4: solve / runs / corrections -------------------
export const Solver = {
  solve: (body: { cycle_id: number; objective_weights?: Record<string, number> | null }) =>
    api<SolveResult>("/phase4/solve", { method: "POST", body }),
  runs: (cycleId?: number) =>
    api<SolverRun[]>("/phase4/runs", {
      query: cycleId ? { cycle_id: cycleId } : undefined,
    }),
  run: (runId: number) => api<RunDetail>(`/phase4/runs/${runId}`),
  compare: (a: number, b: number) =>
    api<RunComparison>("/phase4/runs/compare", { query: { a, b } }),
};

export const Corrections = {
  list: (cycleId?: number, offeringId?: number) =>
    api<Correction[]>("/phase4/corrections", {
      query: { cycle_id: cycleId, offering_id: offeringId },
    }),
  create: (body: {
    cycle_id: number;
    offering_id: number;
    field: string;
    after_value: string;
    reason: string;
    before_value?: string | null;
  }) => api<Correction>("/phase4/corrections", { method: "POST", body }),
};

// ---------------- Phase 6: export / publish ----------------

async function downloadFile(path: string, fileName: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (store.accessToken) headers["Authorization"] = `Bearer ${store.accessToken}`;
  const res = await fetch(new URL(API_BASE + path, window.location.origin).pathname, {
    method: "GET",
    headers,
    credentials: "same-origin",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const Export = {
  excel: (runId: number) =>
    downloadFile(`/phase4/runs/${runId}/export/excel`, `schedule_${runId}.xlsx`),
  pdf: (runId: number) =>
    downloadFile(`/phase4/runs/${runId}/export/pdf`, `schedule_${runId}.pdf`),
};
