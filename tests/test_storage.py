"""Tests for storage utilities."""

import json
from pathlib import Path

import yaml

from code_adapt.storage import (
    parse_duration,
    read_json,
    read_yaml,
    write_json,
    write_yaml,
)


class TestYamlIO:
    def test_roundtrip(self, tmp_path: Path):
        data = {"key": "value", "list": [1, 2, 3]}
        path = tmp_path / "test.yaml"
        write_yaml(path, data)
        result = read_yaml(path)
        assert result == data

    def test_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "a" / "b" / "test.yaml"
        write_yaml(path, {"x": 1})
        assert path.exists()


class TestJsonIO:
    def test_roundtrip(self, tmp_path: Path):
        data = {"count": 42, "items": ["a", "b"]}
        path = tmp_path / "test.json"
        write_json(path, data)
        result = read_json(path)
        assert result == data


class TestParseDuration:
    def test_days(self):
        from datetime import datetime, timedelta
        result = parse_duration("7d")
        expected = datetime.now() - timedelta(days=7)
        assert abs((result - expected).total_seconds()) < 2

    def test_weeks(self):
        from datetime import datetime, timedelta
        result = parse_duration("2w")
        expected = datetime.now() - timedelta(weeks=2)
        assert abs((result - expected).total_seconds()) < 2

    def test_invalid_raises(self):
        import pytest
        with pytest.raises(ValueError):
            parse_duration("abc")
