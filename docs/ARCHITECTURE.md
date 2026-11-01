# Architecture and data semantics

Each spec is a Pydantic discriminated union keyed by part_family. Family
parameters are concrete models, not an unrestricted dict. Numbers are finite,
positive and at most 1000 mm where dimensional; optional features have bounded
ranges. Hole diameter is at most 100 mm, feature count at most eight and each
pattern at most 32 positions. Required edge clearance is at least 1 mm.

Plate/finger: lower-left XY origin, length x, width y, thickness z.
Bracket: base at z=0, upright at x=0, total outer upright height includes the
base thickness. Upright hole positions [y,z] cut along x. The corner region
cannot hold holes. Plate/finger holes are top-face [x,y]. Rounded/tapered edges,
duplicate/overlapping holes and pad-seat conflicts are checked before building.
Enclosure: positive open cavity with a floor, separate flat lid and inset ring
lip. Lid clearance is explicit; the lowest lid surface is 3 mm above the base
in the exported exploded arrangement. Optional posts overlap wall material
and have literal through-hole diameters, not simulated threads or fit promises.

RuleParser classifies only four families, extracts named dimensions/tuples and
units, tracks original spans and qualitative explicit/grammar attribution.
It asks for missing dimensions, ambiguous M4 diameters, hole face/layout and
contradictory constraints. Unsupported language remains unsupported. Optional
defaults are visible assumptions requiring confirmation. Revisions copy the
current spec and patch selected parameters/holes; unchanged fields persist.

SQLite schema version 1 contains projects, revisions and typed-kind records for
jobs with artifact metadata. Initial create is the first migration; future
schema changes must explicitly migrate before changing version. Atomic head
compare-and-swap rejects stale writes with 409. Source and history are immutable.
Selecting old history is undo for viewing; restoring creates a new head.
No token or local secret is stored in SQLite.

One supervisor drains a bounded queue. Trusted app.worker receives only owned
input/output paths and validates JSON again. It dispatches to approved templates,
not eval/exec or arbitrary commands. Windows Job Object containment was actually
observed in generated job metadata; independent wall timeout and cancellation
are retained. stdin is DEVNULL so Windows/pytest capture handles are not inherited.
Queue and artifact budgets prevent unbounded work. Restart marks interrupted
jobs SERVICE_RESTARTED; no generation resumes silently.

Geometry evidence includes OCC validity, positive volume, solid count, expected
bbox within 0.05 mm, analytic through-hole removal volume, STEP bbox/volume/validity
readback, nonempty watertight STL readback and recorded feature positions.
Comparisons use floating tolerances, not exact-zero-error claims. STL cannot
encode engineering units; our export/viewer convention is mm, recorded in JSON.
Spec SHA-256, generator/CadQuery/Python versions and artifact hashes accompany output.

Frontend keeps auth in memory and fetches preview bytes using Bearer headers.
Three.js parses the real STL; missing WebGL has an actionable error while file
downloads remain available. Preview revision ID is shown separately from the
editable draft. No token is placed in a URL. REST bodies are bounded while
receiving (including chunked transfer), then Pydantic validates server-side.
CORS and default bind are localhost-only. Shared-secret demo auth is limited.

No structural, load, torque, thermal, manufacturing, regulatory or fastener-fit
certification is performed. STEP is neutral B-rep, not a native feature tree.
