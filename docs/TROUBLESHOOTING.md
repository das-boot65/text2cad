# Troubleshooting

- Choose Python 3.11/3.12 explicitly with setup -Python. Python 3.14 is not assumed compatible. Use x64; verify the locked OCC wheels install.
- Official native Windows instructions:
  https://cadquery.readthedocs.io/en/latest/installation.html
  Pip worked on the verified host. Conda is a documented fallback, not required.
  If wheels fail, an unverified fallback is a separate conda environment:
  conda create -n text2cad -c conda-forge python=3.11 cadquery
  Then activate it and install FastAPI/Uvicorn/Pydantic/SQLAlchemy/trimesh and
  the test tools with pip, using that conda interpreter directly for uvicorn.
  Rerun geometry/readback checks and record its actual versions; do not pretend
  that this alternate dependency resolution is the validated pip lock.
- First startup probes actual OCC and may take several seconds. Wait for
  CAD worker ready. Concurrent CAD/browser work can cause paging and longer startup. Avoid running multiple test/evaluation processes.
- Run uvicorn with --env-file .env. Copy the entire secret, including trailing
  = padding; never commit it. Expired sessions require signing in again.
- A missing dimension needs an explicit clarification; units are not invented.
  Text patterns support four centered holes; use JSON for other approved positions.
- STEP/STL download is disabled until generation/readback passes. Failed jobs
  keep source/history. Check the error code and correct the request, then retry.
- If WebGL is unavailable, exports still work; enable hardware acceleration or
  use a browser with WebGL. Headless QA used SwiftShader explicitly.
- Port 8001 / 5174 busy: stop only the specific previous app instance. Do not
  kill unrelated Python/Node processes or alter system networking.
- Resource limit: archive old artifacts offline after stopping the app. Do not
  erase designs to conceal validation failures. New jobs are refused at 2 GiB.
- PowerShell: README uses a per-process ExecutionPolicy Bypass, not a global
  policy change. npm.cmd avoids npm.ps1 policy problems.
