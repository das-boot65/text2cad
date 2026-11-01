# Text2CAD interface design

## Tokens

| Role | Light default | Dark |
| --- | --- | --- |
| Workspace | `#f1f4f6` | `#151d24` |
| Surface | `#ffffff` | `#1d2832` |
| Inset/control | `#eaf0f4` | `#253440` |
| Navigation | `#e8eef2` | `#18222c` |
| Text | `#243540` | `#e5eef4` |
| Secondary | `#526675` | `#b2c4d2` |
| Divider | `#c3d0d9` | `#405562` |
| Interactive boundary | `#687f8e` | `#7a94a6` |
| Accent | `#205f87` | `#91c9ed` |
| On accent | `#ffffff` | `#142b3b` |
| Success | `#256147` | `#a3ddbb` |
| Caution | `#76500b` | `#f0ce86` |
| Error | `#a12d3d` | `#ffb6bf` |
| Canvas | `#eef3f6` | `#202d38` |
| Grid / major | `#cbd7df` / `#94aab9` | `#344854` / `#637d8d` |

Typography: system Segoe UI sans; working text 14 px; labels 12–13 px; section titles 16–18 px; project/workspace title 20 px. Monospace/tabular numbers for dimensions, revision IDs and source. Spacing: 4/8/12/16/24/32 px. Corners: 3 px. Dividers, alignment and whitespace carry hierarchy; no dashboard KPI cards, chat bubbles, oversized headings or nested card grid.

## Components and truthful states

App-local `Icon`, `StudioNav`, `Status` and `Notice` support the existing editor and viewer. Native labeled parameter controls display units. The project toolbar separates unsaved draft, confirmed source, active build and displayed geometry revision. Validation explicitly identifies prebuild constraints versus geometry/readback evidence. Exports identify the completed revision being downloaded, including while a different draft is present.

Running, cancelled and failed jobs stay visible near build controls and in the toolbar; source retention is not a success claim. Do not invent percentage progress. Preserve the review checkbox, JSON editor, source attribution, hole positions, assumptions, limits, all four families, history/restore and all five export formats. Earlier revision preview is the existing undo mechanism; do not imply an unimplemented undo/redo stack or selection engine.

## Layout, access and motion

At wide sizes use roughly 264 px requirements and 280 px inspector beside the flexible model, with slim global navigation. At mid-desktop use model plus one secondary task area. At tablet/phone provide Model / Requirements / Parameters views, each reachable by labeled controls. Project navigation collapses into an accessible menu; recent projects and theme switching remain available. Long names and errors wrap; source JSON scrolls within its editor.

Camera tools provide fit/reset, wireframe, zoom and preset views, with labeled keyboard access. Existing orbit/pan gestures remain. Both themes update renderer/grid/model/overlays without changing CAD geometry. Honor reduced motion for camera damping and incidental feedback. Never choreograph model or parameter changes, delay a keyboard action or add an animation dependency.
