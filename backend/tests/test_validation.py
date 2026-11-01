import pytest
from pydantic import ValidationError

from app.parsing import RuleParser
from app.schemas import spec_adapter
from app.validation import validate_spec


@pytest.mark.parametrize("parameter", [float("nan"), float("inf"), 0, -1, 1001])
def test_nonfinite_and_out_of_bounds_dimensions(parameter):
    with pytest.raises(ValidationError):
        spec_adapter.validate_python(
            {
                "part_family": "plate",
                "parameters": {"length_mm": parameter, "width_mm": 25, "thickness_mm": 5},
            }
        )


def test_missing_taper_is_a_question_not_an_invented_value():
    result = RuleParser().parse(
        "Gripper finger length 100 mm width 30 mm thickness 8 mm tapered tip."
    )
    assert result["status"] == "needs_clarification"
    assert any("taper length" in question for question in result["questions"])


def test_overlapping_holes_and_nonfinite_positions():
    spec = {
        "part_family": "plate",
        "parameters": {"length_mm": 60, "width_mm": 25, "thickness_mm": 5},
        "hole_features": [{"diameter_mm": 4, "positions_mm": [[10, 10], [11, 10]]}],
    }
    report = validate_spec(spec_adapter.validate_python(spec))
    assert any(e["code"] == "HOLES_OVERLAP" for e in report["errors"])
    spec["hole_features"][0]["positions_mm"][0] = [float("nan"), 10]
    with pytest.raises(ValidationError):
        spec_adapter.validate_python(spec)


def test_fraction_zero_and_unknown_units_do_not_execute_or_crash():
    assert RuleParser().parse("Plate length 1/0 mm width 25 mm thickness 5 mm")["status"] != "ready"
    assert (
        RuleParser().parse("Plate length 60 feet width 25 feet thickness 5 feet")["status"]
        == "needs_clarification"
    )
