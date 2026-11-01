# Using Text2CAD

Open [the built studio](http://127.0.0.1:8001) while its local server is running. Follow [the README](../README.md) for installation or the optional development server. Copy `TEXT2CAD_SECRET` from this project's local ignored `.env` into **Local secret**, then select **Connect workspace**. No external AI account or API key is required.

## Make your first part

1. Select **New design**. Set **Project name** before confirming the first revision. In **Requirements**, choose a component template or write a supported brief, for example: “Make a 60 x 25 mm base plate, 5 mm thick, with four 4.5 mm clearance holes spaced 40 x 15 mm.”
2. Select **Interpret requirements**. Missing critical dimensions become questions. Answer in **Clarification** and select **Add detail & reinterpret**. Unsupported/invalid requests remain errors rather than invented geometry.
3. Open **Parameters**. Inspect dimensions and units, hole positions, assumptions and the source attribution. Numeric fields use millimeters. Expand **Explicit hole positions & complete source JSON** for advanced fields; malformed JSON blocks generation.
4. Select **Check constraints** if needed. A prebuild constraint pass checks parameters only. It is distinct from geometry validation. Editing parameters makes an earlier draft check stale.
5. Check **I reviewed dimensions, hole positions, optional defaults, and limitations**. Select **Confirm & generate**. This saves immutable source and queues the existing native CAD worker. The toolbar distinguishes queued, building, completed, failed and cancelled states; it does not invent progress percentages.
6. Wait for actual geometry and export readback to pass. **Model** then displays the generated STL, with its revision ID. A saved source revision alone is not a successful CAD build.

The four families are mounting plate, L-bracket, electronics enclosure and gripper finger. This is constrained parametric automation. It cannot generate arbitrary mechanical objects. Text hole syntax supports the documented centered four-hole rectangular pattern; advanced approved holes can be edited in JSON.

## Inspect the model

Drag to orbit, right-drag to pan, or use the mouse wheel. **Reset view** fits the model. **Zoom in/out**, the **Camera** preset/orbit menu and **Wireframe** provide labeled alternatives. Focus the canvas to use arrow keys for pan, plus/minus for zoom and 0 for reset. Switching appearance updates the actual canvas and grid. Reduced motion disables camera damping.

At wide widths, Requirements, Model and Parameters share the workspace. At narrower widths, select the corresponding labeled pane. **Projects & tools** opens recent designs, all six views and appearance switching. Navigation does not discard the current draft.

## Change, reject and restore revisions

With a generated revision open, enter “Increase thickness to 6 mm” in **Design request**, then select **Interpret change**. Review **Review the changes** and the parameter inspector. The studio identifies **Uncommitted draft** while keeping the previous completed geometry visibly labeled. It does not pretend the viewport already reflects unbuilt edits.

Select **Discard proposed changes** to return to the selected confirmed source. To keep the changes, review them, confirm and generate another revision. Invalid requests such as moving a hole beyond the edge remain rejected.

**Revision history** shows immutable confirmed source and changed-field counts. **Preview revision** opens an older source/model without deleting later history. To restore that source as the newest version, review and confirm/generate it again; this creates a new revision. There is no separate native undo/redo stack.

## Validate and export the correct geometry

**Validation** identifies the evidence stage. **CONSTRAINTS PASSED** applies to prebuild parameters. **CHECKS PASSED** with geometry/readback evidence applies to the identified generated revision. Warnings and engineering limits remain visible. After editing a draft, recheck it; an earlier pass is not a certificate for new geometry.

**Exports** names the viewed completed revision and offers STEP, STL, source JSON, validation report and engineering handoff ZIP. **Engineering handoff** in the toolbar downloads the ZIP. If a different draft is present, exports remain for the displayed completed model and explicitly exclude those draft edits. They are unavailable until completed geometry exists. Geometry checks do not certify loads, materials, tolerances or manufacturing suitability.

## Failures, cancellation and evaluation

Use **Cancel active build** in the toolbar or **Cancel generation** beside the inspector controls to cancel a queued/running job. Failed/cancelled jobs retain confirmed source and show their state. **Retry geometry** resubmits the same confirmed revision when available. Correcting parameters and confirming them creates a new source revision instead.

The native worker keeps its existing 60-second bound. Generation can time out on a resource-constrained machine. A timeout must remain a failure. Close competing heavy work and retry, or consult [troubleshooting](TROUBLESHOOTING.md); do not infer success from a saved revision or an older preview.

**Evaluation** displays the stored real parser/geometry report and downloads its raw JSON. It does not launch a new evaluation or present the corrected regression result as a fresh blind hold-out. **Field guide** explains the supported grammar, family limits and full workflow.
