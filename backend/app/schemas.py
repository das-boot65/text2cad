"""Typed editable source specifications; millimetres are canonical."""

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


Dimension = Annotated[float, Field(gt=0, le=1000)]
Nonnegative = Annotated[float, Field(ge=0, le=100)]


class PlateParameters(Strict):
    length_mm: Dimension
    width_mm: Dimension
    thickness_mm: Dimension
    corner_radius_mm: Nonnegative = 0


class BracketParameters(PlateParameters):
    height_mm: Dimension


class EnclosureParameters(Strict):
    length_mm: Dimension
    width_mm: Dimension
    height_mm: Dimension
    wall_mm: Dimension
    lid_clearance_mm: Annotated[float, Field(ge=0.05, le=5)]
    screw_hole_diameter_mm: Nonnegative = 0


class FingerParameters(PlateParameters):
    tip: Literal["flat", "tapered"] = "flat"
    taper_length_mm: Nonnegative = 0
    pad_depth_mm: Nonnegative = 0


class Hole(Strict):
    face: Literal["top", "base", "upright"] = "top"
    diameter_mm: Annotated[float, Field(gt=0, le=100)]
    positions_mm: list[tuple[float, float]] = Field(min_length=1, max_length=32)
    minimum_edge_clearance_mm: Annotated[float, Field(ge=1, le=100)] = 1
    pattern: Literal["explicit"] = "explicit"

    @model_validator(mode="after")
    def finite_positions(self):
        if any(not math.isfinite(v) or abs(v) > 1000 for point in self.positions_mm for v in point):
            raise ValueError("hole positions must be finite and within +/-1000 mm")
        return self


class BaseSpec(Strict):
    schema_version: Literal[1] = 1
    units: Literal["mm"] = "mm"
    hole_features: list[Hole] = Field(default_factory=list, max_length=8)
    material_note: str = Field(default="Unspecified; no material analysis", max_length=200)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    source_text: str = Field(default="", max_length=4000)


class PlateSpec(BaseSpec):
    part_family: Literal["plate"]
    parameters: PlateParameters


class BracketSpec(BaseSpec):
    part_family: Literal["bracket"]
    parameters: BracketParameters


class EnclosureSpec(BaseSpec):
    part_family: Literal["enclosure"]
    parameters: EnclosureParameters


class FingerSpec(BaseSpec):
    part_family: Literal["finger"]
    parameters: FingerParameters


Spec = Annotated[
    PlateSpec | BracketSpec | EnclosureSpec | FingerSpec, Field(discriminator="part_family")
]
spec_adapter = TypeAdapter(Spec)


class ParseInput(Strict):
    text: str = Field(min_length=1, max_length=4000)
    current_revision_id: str | None = Field(default=None, max_length=36)


class RevisionInput(Strict):
    spec: Spec
    parent_id: str | None = Field(default=None, max_length=36)
    confirmed: Literal[True]


class ProjectInput(Strict):
    name: str = Field(min_length=1, max_length=100)


class Login(Strict):
    secret: str = Field(max_length=256)
