"""Sequential ID generation: obs_2026_001 format."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from ..storage import get_adapt_dir, ensure_dir, read_json, write_json

IdPrefix = Literal["obs", "ana", "adp", "plan"]


def _counter_path() -> Path:
    return get_adapt_dir() / "state" / "counter.json"


def _load_counter() -> dict[str, int]:
    path = _counter_path()
    if not path.exists():
        return {"obs": 0, "ana": 0, "adp": 0, "plan": 0}
    return read_json(path)


def _save_counter(counter: dict[str, int]) -> None:
    path = _counter_path()
    ensure_dir(path.parent)
    write_json(path, counter)


def generate_id(prefix: IdPrefix) -> str:
    counter = _load_counter()
    counter[prefix] = counter.get(prefix, 0) + 1
    _save_counter(counter)
    year = datetime.now().year
    seq = str(counter[prefix]).zfill(3)
    return f"{prefix}_{year}_{seq}"
