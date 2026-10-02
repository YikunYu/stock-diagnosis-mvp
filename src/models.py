from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Metric:
    key: str
    label: str
    value: Optional[float]
    unit: str
    period: str
    source: str
    formula: str
    status: str = "valid"
    raw_fields: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    evidence_id: str
    dimension: str
    statement: str
    stance: str
    metric_keys: List[str]
    period: str
    source: str
    confidence: str = "medium"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Diagnosis:
    summary: str
    positive_findings: List[Dict[str, Any]] = field(default_factory=list)
    negative_findings: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    unknowns: List[Dict[str, Any]] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    mode: str = "deterministic"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

