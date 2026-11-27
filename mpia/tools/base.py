from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Uniform return type for analytical tools. `data` is JSON-serializable; every number the
    agent later reports must be traceable to something in here."""
    tool: str
    inputs: dict[str, Any]
    data: dict[str, Any]
    sql: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"tool": self.tool, "inputs": self.inputs, "data": self.data, "sql": self.sql, "notes": self.notes}


def pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new - old) / abs(old)
