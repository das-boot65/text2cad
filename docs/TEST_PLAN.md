# Test plan

scripts/test.ps1 gates Ruff lint/format, mypy, pytest, TypeScript, Vitest and Vite
production build. Tests include independent annotated development grammar cases,
unit conversion, missing/ambiguous constraints, finite typed schemas, holes,
all four geometry families, exact requested hole-removal volume, STEP/STL
readback, enclosure screw posts and both bracket faces.

The API test executes real parse -> confirmed immutable revision -> subprocess
generation -> validated files -> handoff -> patch preserving hole positions.
It rejects absent auth, stale parent heads, false confirmation, invalid geometry,
oversized prompts and unsafe IDs. Separate real worker tests exercise timeout
and cancellation. Streamed-body and non-ASCII credential failures are regressions.

Browser QA requires the two local components running. Playwright waits for true
worker readiness, then tests all four real generated parts, the 3D preview,
revision diff, invalid-hole rejection, history undo, handoff download and tablet
clarification. Screenshots/videos are captured from these runs, not mockups.


Generated evaluation outputs remain local and ignored. Keep regression results separate from any future blind evaluation. Warm in-process geometry timings and subprocess wall-clock timings measure different stages.
