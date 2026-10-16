"""Core data structures shared by every layer of the pipeline.

Everything is a plain dataclass that serialises to JSON via ``to_dict`` so that
results can be stored, diffed, exported and rendered without any hidden state.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# --- Measurement provenance -------------------------------------------------
# Where a number came from. The UI and the exports show this next to every value.
SRC_CAD_GEOMETRY = "CAD geometry"          # measured from drawn entities
SRC_SCHEDULE = "Schedule table"            # read from a schedule/table in the drawings
SRC_PLAN_LABEL = "Plan label"              # read from a text label on the plan (e.g. B200X920)
SRC_SECTION_DIM = "Section dimension"      # DIMENSION entity on a section detail
SRC_LEVEL_TAG = "Level tag"                # derived from level block attributes
SRC_SLAB_TAG = "Slab thickness tag"        # slab thickness block attribute
SRC_DERIVED = "Derived"                    # computed from other measured values
SRC_USER = "User input"                    # entered / confirmed by a user
SRC_MISSING = "Not available"

# --- Statuses ----------------------------------------------------------------
ST_VERIFIED = "Verified"
ST_OK = "OK"
ST_CHECK = "Check"
ST_REVIEW = "Review Required"
ST_MISSING = "Missing Data"
ST_NO_BOQ = "BOQ not provided"
STATUS_ORDER = [ST_VERIFIED, ST_OK, ST_CHECK, ST_REVIEW, ST_MISSING, ST_NO_BOQ]

SEV_INFO, SEV_WARN, SEV_ERROR = "info", "warning", "error"


@dataclass
class SourceRef:
    drawing_id: str
    drawing: str                 # file name
    layer: str = ""
    entity_type: str = ""
    handle: str = ""             # DXF handle; nested entities use "parent>child"
    block: str = ""
    bbox: Optional[list] = None  # [xmin, ymin, xmax, ymax] in metres (drawing coords)
    note: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Measurement:
    name: str
    value: Optional[float]
    unit: str = "m"
    source: str = SRC_MISSING
    detail: str = ""             # human readable provenance ("S-FD.dxf table *T34 row F3")
    ref: Optional[SourceRef] = None
    is_assumption: bool = False

    @property
    def available(self) -> bool:
        return self.value is not None

    def to_dict(self):
        d = asdict(self)
        d["ref"] = self.ref.to_dict() if self.ref else None
        return d


@dataclass
class Flag:
    code: str                    # machine code, e.g. MISSING_THICKNESS
    title: str                   # short label shown in the review queue
    detail: str                  # full explanation of why it was raised
    severity: str = SEV_WARN
    status_impact: str = ST_REVIEW

    def to_dict(self):
        return asdict(self)


@dataclass
class CrossCheck:
    name: str
    expected: Any
    actual: Any
    passed: bool
    detail: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class Element:
    uid: str                     # unique id within a run, e.g. FTG-F3-01
    element_type: str            # footing | column | beam | slab | wall | pedestal | blinding
    mark: str                    # drawing ID / tag ("F3", "L1B1-1"); "" when unidentified
    floor: str = ""
    description: str = ""
    drawing_id: str = ""
    drawing: str = ""
    layer: str = ""
    geometry: list = field(default_factory=list)   # polygon [[x,y],...] in metres
    dims: dict = field(default_factory=dict)       # name -> Measurement
    count: int = 1
    sources: list = field(default_factory=list)    # [SourceRef]
    cross_checks: list = field(default_factory=list)  # [CrossCheck]
    flags: list = field(default_factory=list)      # [Flag]
    confidence: float = 1.0
    confidence_reason: str = ""
    attributes: dict = field(default_factory=dict)

    def dim(self, name) -> Optional[float]:
        m = self.dims.get(name)
        return m.value if m else None

    def to_dict(self):
        return {
            "uid": self.uid, "element_type": self.element_type, "mark": self.mark,
            "floor": self.floor, "description": self.description,
            "drawing_id": self.drawing_id, "drawing": self.drawing, "layer": self.layer,
            "geometry": self.geometry,
            "dims": {k: v.to_dict() for k, v in self.dims.items()},
            "count": self.count,
            "sources": [s.to_dict() for s in self.sources],
            "cross_checks": [c.to_dict() for c in self.cross_checks],
            "flags": [f.to_dict() for f in self.flags],
            "confidence": round(self.confidence, 2),
            "confidence_reason": self.confidence_reason,
            "attributes": self.attributes,
        }


@dataclass
class QuantityRecord:
    """Output of the calculation engine for one element and one quantity type."""
    qid: str
    element_uid: str
    element_type: str
    mark: str
    floor: str
    drawing_id: str
    drawing: str
    layer: str
    quantity_type: str           # concrete_volume | plan_area | blinding_volume ...
    unit: str
    value: Optional[float]
    formula: str                 # symbolic, e.g. "L x W x D"
    substitution: str            # numeric, e.g. "2.600 x 2.200 x 0.450"
    inputs: dict                 # name -> Measurement dict
    assumptions: list = field(default_factory=list)
    status: str = ST_OK
    confidence: float = 1.0
    notes: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
