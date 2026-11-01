export interface Auth {
  token: string;
  session_id: string;
}
export interface Spec {
  schema_version: 1;
  part_family: 'plate' | 'bracket' | 'enclosure' | 'finger';
  units: 'mm';
  parameters: Record<string, number | string>;
  hole_features: Hole[];
  assumptions: string[];
  source_text: string;
  material_note?: string;
}
export interface Hole {
  face: 'top' | 'base' | 'upright';
  diameter_mm: number;
  positions_mm: number[][];
  minimum_edge_clearance_mm: number;
  pattern?: 'explicit';
}
export interface Check {
  check: string;
  status: string;
  measured_mm3?: number;
}
export interface Validation {
  valid: boolean;
  errors?: { code: string; message: string }[];
  checks: Check[];
  warnings: string[];
  bbox_mm?: number[];
  volume_mm3?: number;
  solid_count?: number;
  generation_ms?: number;
  spec_sha256?: string;
  cadquery_version?: string;
}
export interface Job {
  id: string;
  state: string;
  revision_id: string;
  error_code: string | null;
  validation?: Validation;
  elapsed_ms?: number;
  windows_job_limits?: boolean;
}
export interface Project {
  id: string;
  name: string;
  head_id: string | null;
  created_at: string;
  revisions?: Revision[];
}
export interface Revision {
  id: string;
  project_id: string;
  parent_id: string | null;
  created_at: string;
  spec: Spec;
  diff: Diff[];
  generation?: Job | null;
}
export interface Diff {
  path: string;
  before: unknown;
  after: unknown;
}
export interface Parsed {
  status: string;
  parsed_spec: Spec | null;
  partial_spec?: Spec;
  questions: string[];
  source_attribution: { field: string; source: string; span: number[]; confidence: string }[];
  diff?: Diff[];
  validation?: Validation;
}
export interface Evaluation {
  status?: string;
  case_count?: number;
  fully_correct_rate?: number;
  slot_precision?: number;
  slot_recall?: number;
  slot_f1?: number;
  clarification_precision?: number;
  geometry?: { family: string; valid: boolean; generation_ms: number; volume_mm3: number }[];
  by_split?: Record<string, { total: number; passed: number }>;
  methodology?: string;
}
export async function api<T>(path: string, auth: Auth | null, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(auth ? { Authorization: `Bearer ${auth.token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(15000),
  });
  const data = await response.json();
  if (!response.ok)
    throw Error(
      data.message ??
        (typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data.validation?.errors ?? data.detail ?? data.error)) ??
        `Request failed (${response.status})`,
    );
  return data as T;
}
export async function download(path: string, auth: Auth, name: string) {
  const response = await fetch(`/api${path}`, {
    headers: { Authorization: `Bearer ${auth.token}` },
  });
  if (!response.ok) throw Error(`Download failed (${response.status})`);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
