"""Run logging.

CLAUDE.md: "A result that cannot be traced back to its exact inputs is not a
result." Every function that fetches data records what it fetched here, and the
log is written next to the output.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import platform
from pathlib import Path
from typing import Any

logger = logging.getLogger("moroccowater")


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


class RunLog:
    """Accumulates provenance for one pipeline run."""

    def __init__(self, run_name: str) -> None:
        self.run_name = run_name
        self.started = _now()
        self.sources: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.assumptions: list[str] = []
        self.environment = {
            "python": platform.python_version(),
            "platform": platform.platform(),
        }

    def source(self, **fields: Any) -> None:
        """Record a data source. Expected: collection, endpoint, item_ids, bbox,
        datetime, crs, resolution, assets."""
        item_ids = fields.get("item_ids")
        if isinstance(item_ids, (list, tuple)) and len(item_ids) > 12:
            joined = "\n".join(sorted(item_ids)).encode()
            fields["item_ids"] = f"<{len(item_ids)} items>"
            fields["item_ids_sha256"] = hashlib.sha256(joined).hexdigest()
        fields["retrieved_at"] = _now()
        self.sources.append(fields)
        logger.info("source: %s", {k: v for k, v in fields.items() if k != "item_ids"})

    def event(self, kind: str, **fields: Any) -> None:
        self.events.append({"kind": kind, "at": _now(), **fields})
        logger.info("%s: %s", kind, fields)

    def assume(self, text: str) -> None:
        """Flag an assumption. CLAUDE.md requires these be explicit, not buried."""
        self.assumptions.append(text)
        logger.warning("ASSUMPTION: %s", text)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "started": self.started,
            "finished": _now(),
            "environment": self.environment,
            "sources": self.sources,
            "events": self.events,
            "assumptions": self.assumptions,
        }

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, default=str))
        logger.info("provenance written to %s", path)
        return path

    def flat_attrs(self) -> dict[str, str]:
        """Provenance squeezed into xarray/parquet-safe string attrs."""
        return {
            "run_name": self.run_name,
            "started": self.started,
            "sources": json.dumps(self.sources, default=str),
            "assumptions": json.dumps(self.assumptions),
        }
