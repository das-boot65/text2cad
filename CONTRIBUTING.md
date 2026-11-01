# Contributing

Use a native Windows Python 3.11/3.12 environment and Node 24. Run setup and
scripts/test.ps1, then the browser demo. Add independent expected corpus labels
before extending grammar; keep genuinely held-out evaluation separate from tuning.
Geometry changes must preserve checks and export readback. Never weaken a
watertightness assertion to make a template pass. Keep inputs as typed data;
no generated Python, eval/exec, arbitrary shell or user paths. Record measured
outcomes and limitations, do not invent accuracy or manufacturing readiness.
