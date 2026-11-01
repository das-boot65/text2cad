"""Bounded deterministic grammar. It emits data, never executable code."""

import copy
import re
from typing import Protocol

from pydantic import ValidationError

from .schemas import Spec, spec_adapter
from .validation import validate_spec

NUMBER = r"-?(?:\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
UNIT = r'(?:millimeters?|millimetres?|centimeters?|centimetres?|meters?|metres?|inches|inch|mm|cm|in|m|")'
QUANTITY = rf"({NUMBER})\s*({UNIT})(?![a-z])"
FAMILIES = {
    "plate": r"\b(?:plate|baseplate)\b",
    "bracket": r"\bbracket\b",
    "enclosure": r"\b(?:enclosure|box|case)\b",
    "finger": r"\b(?:gripper|finger)\b",
}
ALIASES = {
    "length_mm": r"(?:base\s+)?length",
    "width_mm": r"width",
    "thickness_mm": r"thickness|thick",
    "height_mm": r"(?:wall\s+|upright\s+|outer\s+)?height",
    "wall_mm": r"wall\s+thickness|wall",
    "lid_clearance_mm": r"lid\s+clearance",
    "corner_radius_mm": r"corner\s+radius|fillet(?:\s+radius)?",
    "taper_length_mm": r"taper\s+length",
    "pad_depth_mm": r"pad\s+(?:seat\s+)?depth",
    "screw_hole_diameter_mm": r"screw\s+hole\s+diameter",
}
REQUIRED = {
    "plate": ["length_mm", "width_mm", "thickness_mm"],
    "bracket": ["length_mm", "width_mm", "thickness_mm", "height_mm"],
    "enclosure": ["length_mm", "width_mm", "height_mm", "wall_mm", "lid_clearance_mm"],
    "finger": ["length_mm", "width_mm", "thickness_mm"],
}
DEFAULTS: dict[str, dict] = {
    "plate": {"corner_radius_mm": 0},
    "bracket": {"corner_radius_mm": 0},
    "enclosure": {"screw_hole_diameter_mm": 0},
    "finger": {"corner_radius_mm": 0, "tip": "flat", "taper_length_mm": 0, "pad_depth_mm": 0},
}


def millimetres(number: str, unit: str) -> float:
    if "/" in number:
        numerator, denominator = number.split("/")
        value = float(numerator) / float(denominator)
    else:
        value = float(number)
    unit = unit.lower()
    factor = (
        25.4
        if unit in ('"', "in", "inch", "inches")
        else 10
        if unit.startswith("c")
        else 1
        if unit.startswith(("mm", "milli"))
        else 1000
    )
    return round(value * factor, 6)


def spec_diff(before: dict, after: dict) -> list[dict]:
    differences = []
    for section in ("parameters",):
        for key, value in after[section].items():
            if value != before[section].get(key):
                differences.append(
                    {"path": f"{section}.{key}", "before": before[section].get(key), "after": value}
                )
    if before.get("hole_features") != after.get("hole_features"):
        differences.append(
            {
                "path": "hole_features",
                "before": before.get("hole_features"),
                "after": after.get("hole_features"),
            }
        )
    return differences


class RequirementParser(Protocol):
    def parse(self, text: str, current: Spec | None = None) -> dict: ...


class RuleParser:
    def parse(self, text: str, current: Spec | None = None) -> dict:
        try:
            return self._parse(text, current)
        except (ValueError, ZeroDivisionError):
            return {
                "status": "invalid",
                "parsed_spec": None,
                "questions": [
                    "Invalid numeric quantity; use finite dimensions and nonzero fraction denominators."
                ],
                "source_attribution": [],
                "diff": [],
            }

    def _parse(self, text: str, current: Spec | None = None) -> dict:
        if not 0 < len(text) <= 4000:
            return {
                "status": "invalid",
                "questions": ["Use a prompt of 1–4000 characters."],
                "parsed_spec": None,
            }
        lower = text.lower()
        found = [family for family, pattern in FAMILIES.items() if re.search(pattern, lower)]
        if not current and len(found) != 1:
            return {
                "status": "unsupported" if not found else "needs_clarification",
                "parsed_spec": None,
                "questions": [
                    "Choose exactly one supported family: plate, L-bracket, enclosure or gripper finger."
                ],
                "source_attribution": [],
            }
        family = current.part_family if current else found[0]
        if current and found and found != [family]:
            return {
                "status": "needs_clarification",
                "parsed_spec": None,
                "questions": ["Create a new project to change the part family."],
                "source_attribution": [],
            }
        original = current.model_dump() if current else None
        candidate: dict = (
            copy.deepcopy(original)
            if original
            else {
                "schema_version": 1,
                "part_family": family,
                "units": "mm",
                "parameters": {},
                "hole_features": [],
                "assumptions": [],
            }
        )
        params = candidate["parameters"]
        attribution: list[dict] = []
        questions: list[str] = []
        assignments: dict[str, list[float]] = {}

        def assign(field: str, number: str, unit: str, span: tuple[int, int]):
            try:
                value = millimetres(number, unit)
            except (ValueError, ZeroDivisionError):
                questions.append(f"Invalid numeric quantity for {field}.")
                return
            assignments.setdefault(field, []).append(value)
            params[field] = value
            attribution.append(
                {
                    "field": f"parameters.{field}",
                    "value_mm": value,
                    "span": list(span),
                    "source": text[span[0] : span[1]],
                    "explicit": True,
                    "confidence": "explicit",
                }
            )

        allowed_fields = set(REQUIRED[family]) | set(DEFAULTS[family])
        for field, aliases in ALIASES.items():
            if field not in allowed_fields:
                continue
            prefix_pattern = rf"\b(?:{aliases})\s*(?:of|to|is|=|:)?\s*{QUANTITY}"
            matches = list(re.finditer(prefix_pattern, lower))
            if field == "length_mm":
                matches = [
                    match
                    for match in matches
                    if not lower[: match.start()].rstrip().endswith("taper")
                ]
            if not matches:
                matches = list(re.finditer(rf"{QUANTITY}\s*(?:{aliases})\b", lower))
            for match in matches:
                assign(field, match[1], match[2], match.span())
        # Conventional dimension tuples; final unit explicitly scopes unitless tuple members.
        tuple_pattern = rf"(?P<a>{NUMBER})\s*(?P<au>{UNIT})?\s*(?:x|×|by)\s*(?P<b>{NUMBER})\s*(?P<bu>{UNIT})?(?:\s*(?:x|×|by)\s*(?P<c>{NUMBER})\s*(?P<cu>{UNIT})?)?(?![\d.])"
        tuples = list(re.finditer(tuple_pattern, lower))
        if not current:
            for match in tuples:
                prefix = lower[max(0, match.start() - 20) : match.start()]
                if re.search(r"spac(?:ed|ing)|pattern|pitch", prefix):
                    continue
                unit = match["cu"] or match["bu"] or match["au"]
                if not unit:
                    questions.append("Specify units for the dimension tuple (mm, cm, m or inches).")
                    continue
                fields = [
                    "length_mm",
                    "width_mm",
                    "height_mm" if family in ("enclosure", "bracket") else "thickness_mm",
                ]
                for key, name, own_unit in zip(
                    fields, ["a", "b", "c"], ["au", "bu", "cu"], strict=True
                ):
                    if match[name]:
                        assign(key, match[name], match[own_unit] or unit, match.span())
                break
        if family == "enclosure" and "wall_mm" not in params:
            for match in re.finditer(rf"{QUANTITY}\s*(?:thick\s+)?walls?\b", lower):
                assign("wall_mm", match[1], match[2], match.span())
        if family == "finger" and "tapered" in lower:
            params["tip"] = "tapered"
            if "taper_length_mm" not in params or (
                params["taper_length_mm"] == 0 and "taper_length_mm" not in assignments
            ):
                questions.append("Provide taper length with explicit units for the tapered tip.")
        if family == "finger" and re.search(r"flat\s+tip", lower):
            params.update(tip="flat", taper_length_mm=0)

        if current:
            inward = re.search(
                rf"move\s+(?:the\s+)?holes?\s+inwards?\s*(?:by\s*)?{QUANTITY}", lower
            )
            if inward:
                amount = millimetres(inward[1], inward[2])
                for feature in candidate["hole_features"]:
                    face = feature["face"]
                    width = params["width_mm"] if face == "upright" else params["length_mm"]
                    height = (
                        params.get("height_mm", params["width_mm"])
                        if face == "upright"
                        else params["width_mm"]
                    )
                    feature["positions_mm"] = [
                        [
                            x + amount if x < width / 2 else x - amount,
                            y + amount if y < height / 2 else y - amount,
                        ]
                        for x, y in feature["positions_mm"]
                    ]
                if not candidate["hole_features"]:
                    questions.append("This revision has no holes to move.")
            if re.search(r"move\s+(?:one|a)\s+hole\s+beyond\s+(?:the\s+)?edge", lower):
                if candidate["hole_features"]:
                    candidate["hole_features"][0]["positions_mm"][0] = [
                        params["length_mm"] + 1,
                        params["width_mm"] / 2,
                    ]
                else:
                    questions.append("This revision has no hole to move.")
            if (
                not assignments
                and not inward
                and not re.search(r"beyond\s+(?:the\s+)?edge|flat\s+tip|tapered", lower)
            ):
                questions.append(
                    "Specify a supported parameter and explicit value, e.g. increase thickness to 6 mm."
                )
        else:
            hole_match = re.search(
                rf"(?:(one|two|three|four|\d+)\s+)?{QUANTITY}\s*(?:diameter\s+|clearance\s+|through\s+)*holes?",
                lower,
            )
            if re.search(r"\bm\d+\b", lower) and not hole_match:
                questions.append(
                    "Choose a literal hole diameter in mm (for example 4.5 mm clearance holes); tapped threads are unsupported. M4 alone is not a diameter."
                )
            if re.search(r"\btapped\b|\bthreads?\b", lower):
                questions.append(
                    "Tapped/threaded geometry is unsupported. Confirm plain through-holes with a literal diameter instead."
                )
            if hole_match:
                count_word = hole_match[1] or "1"
                count = {"one": 1, "two": 2, "three": 3, "four": 4}.get(
                    count_word, int(count_word) if count_word.isdigit() else 0
                )
                diameter = millimetres(hole_match[2], hole_match[3])
                face = "base" if family == "bracket" else "top"
                if (
                    family == "bracket"
                    and "upright" in lower
                    and "on base" not in lower
                    and "base holes" not in lower
                ):
                    face = "upright"
                if family == "bracket" and not re.search(
                    r"on (?:the )?(?:base|upright)|base holes|upright holes", lower
                ):
                    questions.append("Specify base or upright as the bracket hole face.")
                spacing = re.search(
                    rf"(?:spaced|spacing|pitch|pattern)\s*(?:of\s*)?({NUMBER})\s*({UNIT})?\s*(?:x|×|by)\s*({NUMBER})\s*({UNIT})",
                    lower,
                )
                edge_match = re.search(rf"{QUANTITY}\s*(?:minimum\s+)?edge\s+clearance", lower)
                clearance = millimetres(edge_match[1], edge_match[2]) if edge_match else 1
                if count == 4 and spacing and "length_mm" in params and "width_mm" in params:
                    dx, dy = (
                        millimetres(spacing[1], spacing[2] or spacing[4]),
                        millimetres(spacing[3], spacing[4]),
                    )
                    width = params["width_mm"] if face == "upright" else params["length_mm"]
                    height = params.get("height_mm", 0) if face == "upright" else params["width_mm"]
                    positions = [
                        [(width - dx) / 2, (height - dy) / 2],
                        [(width + dx) / 2, (height - dy) / 2],
                        [(width - dx) / 2, (height + dy) / 2],
                        [(width + dx) / 2, (height + dy) / 2],
                    ]
                    candidate["hole_features"] = [
                        {
                            "face": face,
                            "diameter_mm": diameter,
                            "positions_mm": positions,
                            "minimum_edge_clearance_mm": clearance,
                        }
                    ]
                    attribution.append(
                        {
                            "field": "hole_features",
                            "span": list(hole_match.span()),
                            "source": text[hole_match.start() : hole_match.end()],
                            "explicit": True,
                            "confidence": "grammar",
                            "note": "Centered rectangular pattern from explicit spacing; minimum edge clearance is 1 mm unless specified.",
                        }
                    )
                else:
                    questions.append(
                        "For text hole patterns provide four holes with explicit rectangular spacing, e.g. four 4.5 mm holes spaced 40 x 15 mm. Edit explicit positions in the structured spec for other counts."
                    )
            elif re.search(r"\bholes?\b", lower) and not re.search(r"\bno\s+holes?\b", lower):
                questions.append(
                    "Provide hole count, literal diameter and positions/rectangular spacing."
                )

        for field, values in assignments.items():
            if len(set(values)) > 1:
                questions.append(f"Conflicting values for {field}: {sorted(set(values))}.")
        for field in REQUIRED[family]:
            if field not in params:
                questions.append(
                    f"Provide {field.replace('_mm', '').replace('_', ' ')} with explicit units."
                )
        for key, value in DEFAULTS[family].items():
            params.setdefault(key, value)
        candidate["source_text"] = text
        if not current:
            candidate["assumptions"] = [
                "Optional edge/tip/pad/screw features use the visible schema defaults unless specified. All interpretation requires confirmation.",
                "Rectangular hole spacing is centered on its designated face; default minimum hole-edge clearance is 1 mm.",
            ]
        if questions:
            return {
                "status": "needs_clarification",
                "parsed_spec": None,
                "partial_spec": candidate,
                "questions": list(dict.fromkeys(questions)),
                "source_attribution": attribution,
                "diff": [],
            }
        try:
            spec = spec_adapter.validate_python(candidate)
        except ValidationError as exc:
            return {
                "status": "invalid",
                "parsed_spec": None,
                "questions": [str(e["msg"]) for e in exc.errors()],
                "source_attribution": attribution,
                "diff": [],
            }
        report = validate_spec(spec)
        return {
            "status": "ready" if report["valid"] else "invalid",
            "parsed_spec": spec.model_dump(),
            "questions": [e["message"] for e in report["errors"]],
            "validation": report,
            "source_attribution": attribution,
            "diff": spec_diff(original, spec.model_dump()) if original else [],
            "patch": spec_diff(original, spec.model_dump()) if original else None,
            "requires_confirmation": True,
        }
