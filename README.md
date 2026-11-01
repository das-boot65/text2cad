# Text2CAD

A local parametric design studio that turns supported plain-English requirements into confirmed, validated CAD geometry. It supports mounting plates, L-brackets, electronics enclosures and gripper fingers using an offline rule parser and trusted CadQuery templates.

## Features

- Explicit units, missing-dimension clarification and reviewable structured parameters.
- Confirmed immutable revisions, source attribution, diffs and older-revision preview.
- Real native geometry, OCC checks and STEP/STL readback validation.
- Model-first Three.js viewer with orbit/pan, zoom, camera presets and wireframe.
- Distinct draft, prebuild, saved-source and generated-geometry states.
- Bounded jobs, cancellation/retry and STEP/STL/JSON/report/handoff exports.
- Responsive requirements/model/parameter panes, recent projects and both themes.

## Run on Windows

Requires native Python 3.11/3.12 x64, Node 24 and Git. PowerShell 5.1 is supported.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
# Optional explicit interpreter:
# powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python 'C:\path\to\python.exe'
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

Open http://127.0.0.1:5174. Setup creates a fresh random `TEXT2CAD_SECRET` in ignored `.env`; use its complete value in the login form. Setup preserves an existing `.env`. Keep the server bound to localhost. Ctrl+C stops the launch script.

After `npm.cmd run build` in `frontend`, `scripts/start.ps1 -BackendOnly` serves the built app at http://127.0.0.1:8001. Local API documentation is at http://127.0.0.1:8001/docs. First-time dependency setup needs internet access; core operation then runs locally.

## Architecture

React studio → offline rule parser → reviewed typed specification → immutable SQLite revision → bounded CadQuery subprocess → geometry/export checks → actual STL viewer and engineering downloads. Editable draft, confirmed source and displayed geometry revision are tracked separately.

[Architecture](docs/ARCHITECTURE.md) · [Use every view](docs/USER_GUIDE.md) · [Interface design](DESIGN.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Security](SECURITY.md)

## Verify and reproduce

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
# With the backend and frontend running:
cd frontend
npx.cmd playwright install chromium
npm.cmd run e2e
```

See [the test plan](docs/TEST_PLAN.md) for coverage and boundaries. Run `.\.venv\Scripts\python.exe scripts/evaluate.py` to generate local parser/geometry results. The authored corpus is an internal constrained-grammar check, not an external benchmark or general-language accuracy claim. Evaluation initially shows `not_run` until a local result file exists.

## Publication boundary

This is a source-only publication. Screenshots, recordings, local designs, databases, raw traces, measured reports and original development history remain outside this repository. The scripts can reproduce local outputs, which are ignored by Git. No private data is needed to use the applications. Synthetic, authored test inputs are included with the tests.

Enable the included commit and push checks with `git config core.hooksPath .githooks`.

## Limits

Exactly four constrained template families are supported; arbitrary text-to-any-CAD and optional LLM integration are not implemented. Geometry validation does not certify stress, material choice, tolerances, fastener fit or manufacturing suitability. Native jobs retain a 60-second timeout and can fail under resource pressure; saved source is not proof of a successful build. The localhost shared-secret session is not internet-facing authentication.

Windows QA automation is included, with hosted execution disabled to keep generated logs and reports local. Its presence is not a claim that every physical-device, browser and assistive-technology combination has been validated. MIT applies to authored source; dependencies retain their own licenses.
