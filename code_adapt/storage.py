"""YAML/JSON file I/O with atomic writes for the .adapt/ directory."""

from __future__ import annotations

import json
import os
import secrets
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


# --- Adapt directory helpers --------------------------------------------------


def get_adapt_dir() -> Path:
    return Path.cwd() / ".adapt"


def is_initialized() -> bool:
    adapt_dir = get_adapt_dir()
    return adapt_dir.exists() and (adapt_dir / "config.yaml").exists()


def ensure_dir(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)


# --- YAML I/O ----------------------------------------------------------------


def read_yaml(file_path: Path) -> Any:
    return yaml.safe_load(file_path.read_text(encoding="utf-8"))


def write_yaml(file_path: Path, data: Any) -> None:
    content = yaml.dump(data, default_flow_style=False, allow_unicode=True, width=1000)
    _atomic_write(file_path, content)


# --- JSON I/O ----------------------------------------------------------------


def read_json(file_path: Path) -> Any:
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json(file_path: Path, data: Any) -> None:
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _atomic_write(file_path, content)


# --- Atomic write -------------------------------------------------------------


def _atomic_write(file_path: Path, content: str) -> None:
    ensure_dir(file_path.parent)
    tmp = file_path.parent / f".tmp-{secrets.token_hex(6)}"
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(file_path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


# --- Duration parser ----------------------------------------------------------


def parse_duration(input_str: str) -> datetime:
    match = re.match(r"^(\d+)([dwmM])$", input_str)
    if not match:
        raise ValueError(f'Invalid duration format: "{input_str}". Use formats like 7d, 2w, 1m.')

    amount = int(match.group(1))
    unit = match.group(2)
    now = datetime.now()

    if unit == "d":
        from datetime import timedelta
        return now - timedelta(days=amount)
    elif unit == "w":
        from datetime import timedelta
        return now - timedelta(weeks=amount)
    elif unit in ("m", "M"):
        month = now.month - amount
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        day = min(now.day, _days_in_month(year, month))
        return now.replace(year=year, month=month, day=day)

    raise ValueError(f'Invalid duration unit: "{unit}"')


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]
