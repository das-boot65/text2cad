import json
from pathlib import Path

import pytest

from app.parsing import RuleParser, millimetres
from app.schemas import spec_adapter

CORPUS = json.loads(
    (Path(__file__).resolve().parents[2] / "examples/prompts/corpus.json").read_text(
        encoding="utf-8"
    )
)["cases"]


@pytest.mark.parametrize(
    "case", [c for c in CORPUS if c["split"] == "development"], ids=lambda c: c["id"]
)
def test_development_corpus(case):
    current = spec_adapter.validate_python(case["current_spec"]) if "current_spec" in case else None
    result = RuleParser().parse(case["text"], current)
    assert result["status"] == case["expected_status"], result.get("questions")
    if case["expected_status"] == "ready":
        assert result["parsed_spec"]["part_family"] == case["family"]
        for key, value in case["expected_slots"].items():
            assert result["parsed_spec"]["parameters"][key] == pytest.approx(value)
        if case.get("preserve_holes"):
            assert result["parsed_spec"]["hole_features"] == current.model_dump()["hole_features"]
        for attribution in result["source_attribution"]:
            start, end = attribution["span"]
            assert case["text"][start:end] == attribution["source"]


def test_units_and_missing_value_are_not_assumed():
    assert millimetres("1/4", "inch") == 6.35
    assert millimetres("0.06", "m") == 60
    assert (
        RuleParser().parse("Plate length 60 width 25 thickness 5")["status"]
        == "needs_clarification"
    )


def test_revision_diff_and_out_of_bounds_hole():
    base = RuleParser().parse("Plate 60 x 25 mm, 5 mm thick, four 4.5 mm holes spaced 40 x 15 mm.")[
        "parsed_spec"
    ]
    current = spec_adapter.validate_python(base)
    change = RuleParser().parse("Increase thickness to 6 mm.", current)
    assert change["diff"] == [{"path": "parameters.thickness_mm", "before": 5, "after": 6}]
    assert change["parsed_spec"]["hole_features"] == base["hole_features"]
    invalid = RuleParser().parse("Move one hole beyond the edge.", current)
    assert invalid["status"] == "invalid"
    assert any("clearance" in question for question in invalid["questions"])
