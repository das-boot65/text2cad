import pytest

from app.cad import generate


@pytest.mark.parametrize(
    "family,parameters,solids",
    [
        ("plate", {"length_mm": 60, "width_mm": 25, "thickness_mm": 5}, 1),
        ("bracket", {"length_mm": 60, "width_mm": 25, "thickness_mm": 5, "height_mm": 40}, 1),
        (
            "enclosure",
            {
                "length_mm": 80,
                "width_mm": 50,
                "height_mm": 30,
                "wall_mm": 3,
                "lid_clearance_mm": 0.3,
            },
            2,
        ),
        (
            "finger",
            {
                "length_mm": 80,
                "width_mm": 20,
                "thickness_mm": 6,
                "tip": "tapered",
                "taper_length_mm": 20,
                "pad_depth_mm": 1,
            },
            1,
        ),
    ],
)
def test_family_generation_readback_and_bounds(tmp_path, family, parameters, solids):
    report = generate({"part_family": family, "parameters": parameters}, tmp_path)
    assert report["valid"] and report["solid_count"] == solids
    assert all(c["status"] == "pass" for c in report["checks"])
    assert (tmp_path / "model.step").stat().st_size > 0
    assert (tmp_path / "model.stl").stat().st_size > 0


def test_plate_holes_removed_as_requested(tmp_path):
    report = generate(
        {
            "part_family": "plate",
            "parameters": {"length_mm": 60, "width_mm": 25, "thickness_mm": 5},
            "hole_features": [
                {
                    "face": "top",
                    "diameter_mm": 4.5,
                    "positions_mm": [[10, 5], [50, 5], [10, 20], [50, 20]],
                }
            ],
        },
        tmp_path,
    )
    check = next(c for c in report["checks"] if c["check"] == "hole_removal_volume")
    assert check["requested_through_holes"] == 4
    assert check["expected_removed_mm3"] == pytest.approx(check["actual_removed_mm3"])


def test_invalid_hole_never_generated(tmp_path):
    with pytest.raises(ValueError):
        generate(
            {
                "part_family": "plate",
                "parameters": {"length_mm": 60, "width_mm": 25, "thickness_mm": 5},
                "hole_features": [{"diameter_mm": 4.5, "positions_mm": [[70, 5]]}],
            },
            tmp_path,
        )
    assert not (tmp_path / "model.step").exists()


def test_bracket_both_faces_and_enclosure_screw_posts(tmp_path):
    bracket = {
        "part_family": "bracket",
        "parameters": {"length_mm": 60, "width_mm": 30, "height_mm": 40, "thickness_mm": 5},
        "hole_features": [
            {"face": "base", "diameter_mm": 4, "positions_mm": [[20, 10], [45, 20]]},
            {"face": "upright", "diameter_mm": 4, "positions_mm": [[10, 20], [20, 30]]},
        ],
    }
    report = generate(bracket, tmp_path / "bracket")
    assert report["valid"]
    enclosure = {
        "part_family": "enclosure",
        "parameters": {
            "length_mm": 100,
            "width_mm": 80,
            "height_mm": 30,
            "wall_mm": 3,
            "lid_clearance_mm": 0.3,
            "screw_hole_diameter_mm": 3,
        },
    }
    report = generate(enclosure, tmp_path / "enclosure")
    assert report["valid"] and report["solid_count"] == 2
