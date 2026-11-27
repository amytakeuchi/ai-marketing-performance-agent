"""Executes analytical tools with timing, audit logging and uniform error handling."""
from __future__ import annotations

import time

from ..tools.base import ToolResult


class ToolError(RuntimeError):
    def __init__(self, tool: str, original: Exception):
        super().__init__(f"{tool} failed: {original}")
        self.tool, self.original = tool, original


class ToolRunner:
    def __init__(self, audit=None, investigation_id: str | None = None, node: str = "analyze"):
        self.audit, self.inv, self.node = audit, investigation_id, node

    def _summary(self, tr: ToolResult) -> dict:
        s = {"keys": list(tr.data.keys())}
        for k, v in tr.data.items():
            if isinstance(v, list):
                s[f"n_{k}"] = len(v)
        return s

    def __call__(self, fn, *args, **kwargs) -> ToolResult:
        name = fn.__name__
        t0 = time.perf_counter()
        try:
            tr = fn(*args, **kwargs)
        except Exception as e:
            if self.audit and self.inv:
                safe = {k: v for k, v in kwargs.items()}
                self.audit.log_tool_call(self.inv, self.node, name, {"args": [str(a) for a in args[1:]], **safe}, None, None,
                                         "error", f"{type(e).__name__}: {e}", int((time.perf_counter() - t0) * 1000))
            raise ToolError(name, e) from e
        if self.audit and self.inv:
            self.audit.log_tool_call(self.inv, self.node, name, tr.inputs, self._summary(tr), tr.sql, "ok", None,
                                     int((time.perf_counter() - t0) * 1000))
        return tr
