"""Prebuild checks independent of OpenCascade."""

import math

from .schemas import BracketSpec, EnclosureSpec, FingerSpec, Spec

WARNINGS = [
    "Structural stress, torque, thermal behavior and regulatory safety are not checked.",
    "Manufacturing tolerances, print orientation, material choice and fastener fit are not certified.",
    "STEP is a neutral B-rep export; confirmed JSON and the template are the editable source.",
]


def validate_spec(spec: Spec) -> dict:
    p = spec.parameters
    errors: list[dict] = []

    def check(valid: bool, code: str, message: str):
        if not valid:
            errors.append({"code": code, "message": message})

    if isinstance(spec, EnclosureSpec):
        check(
            min(p.length_mm, p.width_mm, p.height_mm) > 2 * p.wall_mm,  # type: ignore[union-attr]
            "CAVITY_INVALID",
            "Wall thickness must leave a positive cavity.",
        )
        check(
            min(p.length_mm, p.width_mm) > 4 * p.wall_mm + 2 * p.lid_clearance_mm,  # type: ignore[union-attr]
            "LID_LIP_INVALID",
            "Lid clearance and wall thickness must leave a valid inset lip.",
        )
        if p.screw_hole_diameter_mm:  # type: ignore[union-attr]
            check(
                min(p.length_mm, p.width_mm) > 2 * p.wall_mm + 10 * p.screw_hole_diameter_mm,  # type: ignore[union-attr]
                "SCREW_POSTS_OVERLAP",
                "Enclosure is too small for the requested screw posts.",
            )
        check(
            not spec.hole_features,
            "ENCLOSURE_HOLES_UNSUPPORTED",
            "Use screw_hole_diameter_mm for enclosure screw points.",
        )
    else:
        check(
            p.thickness_mm <= min(p.length_mm, p.width_mm),  # type: ignore[union-attr]
            "THICKNESS_EXCESSIVE",
            "Thickness exceeds the smaller planar dimension.",
        )
        radius = p.corner_radius_mm  # type: ignore[union-attr]
        check(
            radius < min(p.length_mm, p.width_mm) / 2,
            "CORNER_RADIUS_EXCESSIVE",
            "Corner radius exceeds available material.",
        )
        if isinstance(spec, BracketSpec):
            check(
                spec.parameters.height_mm > spec.parameters.thickness_mm,
                "HEIGHT_INVALID",
                "Upright height must exceed base thickness.",
            )
            check(
                radius == 0 or radius < spec.parameters.thickness_mm / 2,
                "BRACKET_FILLET_EXCESSIVE",
                "Bracket fillet radius must be less than half thickness.",
            )
        if isinstance(spec, FingerSpec):
            fp = spec.parameters
            check(
                fp.pad_depth_mm < fp.thickness_mm,
                "PAD_DEPTH_INVALID",
                "Pad seat must not cut through the finger.",
            )
            check(
                (fp.tip == "flat" and fp.taper_length_mm == 0)
                or (fp.tip == "tapered" and 0 < fp.taper_length_mm <= fp.length_mm / 2),
                "TAPER_INVALID",
                "Tapered tip requires a taper length up to half the finger length; flat tip requires zero.",
            )
            check(
                not (fp.tip == "tapered" and radius),
                "ROUNDED_TAPER_UNSUPPORTED",
                "Tapered finger with corner rounds is not a supported combination.",
            )

    seen: list[tuple[str, float, float, float]] = []
    for feature_index, feature in enumerate(spec.hole_features):
        face = feature.face
        allowed = {"base", "upright"} if isinstance(spec, BracketSpec) else {"top"}
        check(
            face in allowed,
            "FACE_INVALID",
            f"Hole feature {feature_index}: face {face} is not supported for this family.",
        )
        face_length = spec.parameters.width_mm if face == "upright" else p.length_mm
        face_width = (
            spec.parameters.height_mm
            if face == "upright" and isinstance(spec, BracketSpec)
            else p.width_mm
        )
        radius = feature.diameter_mm / 2
        margin = radius + feature.minimum_edge_clearance_mm
        for x, y in feature.positions_mm:
            check(
                margin <= x <= face_length - margin and margin <= y <= face_width - margin,
                "HOLE_EDGE_CLEARANCE",
                f"Hole ({x}, {y}) on {face} violates boundary/edge clearance.",
            )
            if isinstance(spec, BracketSpec):
                distance = y if face == "upright" else x
                check(
                    distance >= spec.parameters.thickness_mm + margin,
                    "HOLE_BLOCKED_BY_WALL",
                    "Hole intersects the bracket corner material.",
                )
            if isinstance(spec, FingerSpec):
                fp = spec.parameters
                if fp.tip == "tapered" and x > fp.length_mm - fp.taper_length_mm:
                    lower = (
                        (x - (fp.length_mm - fp.taper_length_mm))
                        * fp.width_mm
                        / (4 * fp.taper_length_mm)
                    )
                    slope = fp.width_mm / (4 * fp.taper_length_mm)
                    check(
                        y - lower >= margin * math.sqrt(1 + slope**2)
                        and fp.width_mm - lower - y >= margin * math.sqrt(1 + slope**2),
                        "HOLE_IN_TAPER",
                        "Hole is too close to a tapered edge.",
                    )
                if fp.pad_depth_mm:
                    check(
                        x + margin < fp.length_mm * 0.7,
                        "PAD_HOLE_OVERLAP",
                        "Mounting holes must stay outside the pad-seat region.",
                    )
            if not isinstance(spec, EnclosureSpec) and spec.parameters.corner_radius_mm:
                corner = spec.parameters.corner_radius_mm
                if (x < corner or x > face_length - corner) and (
                    y < corner or y > face_width - corner
                ):
                    cx = corner if x < corner else face_length - corner
                    cy = corner if y < corner else face_width - corner
                    check(
                        math.hypot(x - cx, y - cy) + margin <= corner,
                        "HOLE_ROUNDED_CORNER",
                        "Hole clearance intersects a rounded corner.",
                    )
            for other_face, ox, oy, other_radius in seen:
                if other_face == face:
                    check(
                        math.hypot(x - ox, y - oy) > radius + other_radius,
                        "HOLES_OVERLAP",
                        "Holes on the same face overlap or duplicate.",
                    )
            seen.append((face, x, y, radius))
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": WARNINGS,
        "units": "mm",
        "checks": [{"check": "prebuild_constraints", "status": "fail" if errors else "pass"}],
        "tolerance_mm": 0.05,
    }
