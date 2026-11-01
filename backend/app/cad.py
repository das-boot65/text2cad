"""Approved CadQuery templates and geometric evidence. No generated code."""

import hashlib
import json
import math
import platform
import time
from pathlib import Path
from typing import cast

import cadquery as cq
import trimesh

from .schemas import BracketSpec, EnclosureSpec, FingerSpec, Spec, spec_adapter
from .validation import WARNINGS, validate_spec


def box(length: float, width: float, height: float, origin=(0, 0, 0)):
    return (
        cq.Workplane("XY")
        .box(length, width, height, centered=(False, False, False))
        .translate(origin)
    )


def cylinder(radius: float, length: float, origin: tuple, axis=(0, 0, 1)):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*axis))
    )


def build(spec: Spec):
    report = validate_spec(spec)
    if not report["valid"]:
        raise ValueError(json.dumps(report["errors"]))
    p = spec.parameters
    length, width = p.length_mm, p.width_mm
    extra_holes = 0
    if isinstance(spec, EnclosureSpec):
        ep = spec.parameters
        wall, height, gap = ep.wall_mm, ep.height_mm, ep.wall_mm + 3.0
        base = box(length, width, height).cut(
            box(length - 2 * wall, width - 2 * wall, height, (wall, wall, wall))
        )
        lid = box(length, width, wall, (0, 0, height + gap))
        inset = wall + ep.lid_clearance_mm
        # Inset lip is a ring; its outer size leaves the explicit lid clearance.
        lip = box(length - 2 * inset, width - 2 * inset, wall, (inset, inset, height + gap - wall))
        inner_length, inner_width = length - 2 * inset - 2 * wall, width - 2 * inset - 2 * wall
        lip = lip.cut(
            box(inner_length, inner_width, wall, (inset + wall, inset + wall, height + gap - wall))
        )
        lid = lid.union(lip)
        if ep.screw_hole_diameter_mm:
            diameter = ep.screw_hole_diameter_mm
            post_radius = diameter * 1.5
            # Overlap wall material rather than creating a tangent nonmanifold mesh edge.
            offset = wall + post_radius - min(wall * 0.5, post_radius * 0.25)
            for x, y in [
                (offset, offset),
                (length - offset, offset),
                (offset, width - offset),
                (length - offset, width - offset),
            ]:
                base = base.union(cylinder(post_radius, height - wall, (x, y, wall)))
                base = base.cut(cylinder(diameter / 2, height + 2, (x, y, -1)))
                lid = lid.cut(cylinder(diameter / 2, wall * 3 + gap, (x, y, height)))
            extra_holes = 8
        shape = cq.Workplane("XY").add(cq.Compound.makeCompound([base.val(), lid.val()]))
        expected_bbox = [length, width, height + gap + wall]
        expected_solids = 2
    elif isinstance(spec, BracketSpec):
        bp = spec.parameters
        shape = box(length, width, bp.thickness_mm).union(box(bp.thickness_mm, width, bp.height_mm))
        if bp.corner_radius_mm:
            shape = shape.edges("|Z").fillet(bp.corner_radius_mm)
        expected_bbox, expected_solids = [length, width, bp.height_mm], 1
    else:
        thickness = spec.parameters.thickness_mm
        if isinstance(spec, FingerSpec) and spec.parameters.tip == "tapered":
            taper = spec.parameters.taper_length_mm
            polygon = [
                (0, 0),
                (length - taper, 0),
                (length, width / 4),
                (length, width * 3 / 4),
                (length - taper, width),
                (0, width),
            ]
            shape = cq.Workplane("XY").polyline(polygon).close().extrude(thickness)
        else:
            shape = box(length, width, thickness)
            if spec.parameters.corner_radius_mm:
                shape = shape.edges("|Z").fillet(spec.parameters.corner_radius_mm)
        if isinstance(spec, FingerSpec) and spec.parameters.pad_depth_mm:
            shape = shape.cut(
                box(
                    length * 0.25,
                    width * 0.4,
                    spec.parameters.pad_depth_mm,
                    (length * 0.7, width * 0.3, thickness - spec.parameters.pad_depth_mm),
                )
            )
        expected_bbox, expected_solids = [length, width, thickness], 1
    before_holes = cast(cq.Shape, shape.val()).Volume()
    expected_removed = 0.0
    for feature in spec.hole_features:
        if isinstance(spec, EnclosureSpec):
            raise TypeError(
                "Enclosure uses the approved screw-point parameter instead of hole features"
            )
        for x, y in feature.positions_mm:
            thickness = spec.parameters.thickness_mm
            if feature.face == "upright":
                cut = cylinder(feature.diameter_mm / 2, thickness + 2, (-1, x, y), (1, 0, 0))
            else:
                cut = cylinder(feature.diameter_mm / 2, thickness + 2, (x, y, -1))
            shape = shape.cut(cut)
            expected_removed += math.pi * (feature.diameter_mm / 2) ** 2 * thickness
    actual_removed = before_holes - cast(cq.Shape, shape.val()).Volume()
    if not math.isclose(expected_removed, actual_removed, rel_tol=1e-6, abs_tol=1e-5):
        raise ValueError("Hole removal volume does not match the confirmed through-hole features")
    return (
        shape,
        expected_bbox,
        expected_solids,
        {
            "requested_through_holes": sum(len(h.positions_mm) for h in spec.hole_features),
            "enclosure_screw_holes": extra_holes,
            "expected_removed_mm3": expected_removed,
            "actual_removed_mm3": actual_removed,
            "hole_positions": [h.model_dump() for h in spec.hole_features],
        },
    )


def generate(spec_data: dict, directory: Path) -> dict:
    begin = time.perf_counter()
    spec = spec_adapter.validate_python(spec_data)
    shape, expected_bbox, expected_solids, features = build(spec)
    solid = cast(cq.Shape, shape.val())
    bounds = solid.BoundingBox()
    bbox = [bounds.xlen, bounds.ylen, bounds.zlen]
    checks: list[dict] = [
        {"check": "occ_valid", "status": "pass" if solid.isValid() else "fail"},
        {
            "check": "positive_volume",
            "status": "pass" if solid.Volume() > 0 else "fail",
            "measured_mm3": solid.Volume(),
        },
        {
            "check": "solid_count",
            "status": "pass" if len(solid.Solids()) == expected_solids else "fail",
            "measured": len(solid.Solids()),
            "expected": expected_solids,
        },
        {
            "check": "bounding_box",
            "status": "pass"
            if all(abs(a - b) <= 0.05 for a, b in zip(bbox, expected_bbox, strict=True))
            else "fail",
            "measured_mm": bbox,
            "expected_mm": expected_bbox,
            "tolerance_mm": 0.05,
        },
        {"check": "hole_removal_volume", "status": "pass", **features},
    ]
    if any(c["status"] == "fail" for c in checks):
        raise ValueError("Postbuild geometry checks failed")
    directory.mkdir(parents=True, exist_ok=True)
    step, stl = directory / "model.step", directory / "model.stl"
    cq.exporters.export(shape, str(step))
    cq.exporters.export(shape, str(stl), tolerance=0.02, angularTolerance=0.1)
    reread = cast(cq.Shape, cq.importers.importStep(str(step)).val())
    rb = reread.BoundingBox()
    readback_bbox = [rb.xlen, rb.ylen, rb.zlen]
    step_valid = (
        reread.isValid()
        and math.isclose(reread.Volume(), solid.Volume(), rel_tol=1e-6)
        and all(abs(a - b) < 0.05 for a, b in zip(readback_bbox, bbox, strict=True))
    )
    mesh = cast(trimesh.Trimesh, trimesh.load(str(stl), force="mesh"))
    stl_valid = (
        len(mesh.faces) > 0
        and mesh.is_watertight
        and all(abs(float(a) - b) < 0.05 for a, b in zip(mesh.extents, bbox, strict=True))
    )
    checks += [
        {"check": "step_readback", "status": "pass" if step_valid else "fail"},
        {
            "check": "stl_readback",
            "status": "pass" if stl_valid else "fail",
            "triangles": len(mesh.faces),
            "watertight": bool(mesh.is_watertight),
        },
    ]
    canonical = json.dumps(spec.model_dump(), sort_keys=True, separators=(",", ":"))
    report = {
        "valid": all(c["status"] == "pass" for c in checks),
        "checks": checks,
        "warnings": WARNINGS,
        "units": "mm",
        "bbox_mm": bbox,
        "volume_mm3": solid.Volume(),
        "solid_count": len(solid.Solids()),
        "generator_version": "1.0.0",
        "cadquery_version": cq.__version__,
        "python": platform.python_version(),
        "spec_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "generation_ms": (time.perf_counter() - begin) * 1000,
        "preview_lid_gap_mm": 3 if isinstance(spec, EnclosureSpec) else None,
    }
    if not report["valid"]:
        raise ValueError("Export readback validation failed")
    (directory / "spec.json").write_text(json.dumps(spec.model_dump(), indent=2), encoding="utf-8")
    (directory / "validation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
