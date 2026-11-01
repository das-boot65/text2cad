# API guide

Open /docs or /openapi.json on the local backend for exact typed schemas.
POST /api/sessions {secret} -> one-hour memory-only bearer token.
All design mutations and artifact reads use Authorization: Bearer TOKEN.
GET /api/health checks an actual CAD probe, supervisor and DB. A failed probe
leaves the service unready; generation returns 503 rather than fake success.

- GET /api/parts/families: supported families, required fields and JSON schema.
- POST /api/parse {text,current_revision_id?}: ready/needs_clarification/invalid/
  unsupported, normalized spec, questions, source attribution and optional patch.
- POST /api/validate: prebuild spec checks; no geometry generation.
- POST /api/projects {name}, GET /api/projects, GET /api/projects/{id}.
- POST /api/projects/{id}/revisions {spec,parent_id,confirmed:true}; false or
  missing confirmation is rejected, stale head returns 409.
- GET /api/revisions/{id}, POST /api/revisions/{id}/generate -> bounded job.
- GET /api/jobs/{id}; POST /api/jobs/{id}/cancel.
- GET /api/revisions/{id}/validation.
- GET /api/revisions/{id}/downloads/{step|stl|json|report}.
- GET /api/revisions/{id}/handoff.
- GET /api/evaluation: actual reproducible result file, or explicit not_run.

Invalid typed/geometry input returns 422 with actionable details; missing/expired
auth 401; unknown IDs/formats 404; pre-generation artifact read 409; queue/disk
budget 429; missing CAD worker 503; streamed HTTP body >64 KiB 413. UUID route
parameters and whitelisted filenames prevent user-controlled filesystem access.
Responses include correlation ID headers. Prompt length is 1–4000 characters.

Jobs transition queued -> running -> completed/failed/cancelled. Error codes
include GENERATION_TIMEOUT, GEOMETRY_GENERATION_FAILED, SERVICE_RESTARTED and
SUPERVISOR_FAILURE. A failed job preserves its confirmed source revision; it
does not expose a supposedly validated export.
