"""Tests for TOON utility module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hero.state.toon import (
    json_to_toon,
    toon_read,
    toon_write,
)


class TestToonRead:
    """Tests for toon_read function."""

    def test_simple_key_value(self, tmp_path: Path) -> None:
        """Test reading simple key-value pairs."""
        toon_content = "name: test\nvalue: 123\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"name": "test", "value": 123}

    def test_list_format(self, tmp_path: Path) -> None:
        """Test reading list format key[count]: val1, val2."""
        toon_content = "items[3]: 1, 2, 3\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"items": [1, 2, 3]}

    def test_nested_dict(self, tmp_path: Path) -> None:
        """Test reading nested dictionaries."""
        toon_content = "nested:\n  key: value\n  count: 42\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"nested": {"key": "value", "count": 42}}

    def test_comments_ignored(self, tmp_path: Path) -> None:
        """Test that comments are stripped."""
        toon_content = "name: test # this is a comment\nvalue: 123 # comment\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"name": "test", "value": 123}

    def test_empty_list(self, tmp_path: Path) -> None:
        """Test reading empty list."""
        toon_content = "items[0]: \n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"items": []}

    def test_boolean_values(self, tmp_path: Path) -> None:
        """Test reading boolean values."""
        toon_content = "enabled: true\ndisabled: false\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"enabled": True, "disabled": False}

    def test_float_values(self, tmp_path: Path) -> None:
        """Test reading float values."""
        toon_content = "pi: 3.14\nprecise: 2.71828\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        result = toon_read(path)

        assert result == {"pi": 3.14, "precise": 2.71828}

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Test that reading a nonexistent file returns an empty dict."""
        path = tmp_path / "nonexistent.toon"
        result = toon_read(path)
        assert result == {}


class TestToonWrite:
    """Tests for toon_write function."""

    def test_simple_key_value(self, tmp_path: Path) -> None:
        """Test writing simple key-value pairs."""
        path = tmp_path / "output.toon"
        data = {"name": "test", "value": 123}

        toon_write(path, data)

        result = path.read_text()
        assert "name" in result and "test" in result
        assert "value: 123" in result

    def test_list_format(self, tmp_path: Path) -> None:
        """Test writing lists in key[count]: val1, val2 format."""
        path = tmp_path / "output.toon"
        data = {"items": [1, 2, 3]}

        toon_write(path, data)

        result = path.read_text()
        assert "items[3]: 1, 2, 3" in result

    def test_nested_dict(self, tmp_path: Path) -> None:
        """Test writing nested dictionaries."""
        path = tmp_path / "output.toon"
        data = {"nested": {"key": "value", "count": 42}}

        toon_write(path, data)

        result = path.read_text()
        assert "nested:" in result
        assert "key" in result and "value" in result
        assert "count: 42" in result

    def test_empty_list(self, tmp_path: Path) -> None:
        """Test writing empty list."""
        path = tmp_path / "output.toon"
        data = {"items": []}

        toon_write(path, data)

        result = path.read_text()
        assert "items[0]:" in result


class TestRoundTrip:
    """Tests for round-trip conversion dict -> TOON -> dict."""

    def test_simple_dict_roundtrip(self, tmp_path: Path) -> None:
        """Test round-trip with simple dictionary."""
        original = {"name": "test", "value": 42}
        path = tmp_path / "roundtrip.toon"

        toon_write(path, original)
        parsed = toon_read(path)

        assert parsed == original

    def test_dict_with_lists_roundtrip(self, tmp_path: Path) -> None:
        """Test round-trip with lists."""
        original = {"name": "test", "items": [1, 2, 3], "tags": ["a", "b", "c"]}
        path = tmp_path / "roundtrip.toon"

        toon_write(path, original)
        parsed = toon_read(path)

        assert parsed == original

    def test_dict_with_nested_roundtrip(self, tmp_path: Path) -> None:
        """Test round-trip with nested dictionaries."""
        original = {"name": "test", "nested": {"a": 1, "b": 2, "inner": {"c": 3}}}
        path = tmp_path / "roundtrip.toon"

        toon_write(path, original)
        parsed = toon_read(path)

        assert parsed == original

    def test_mixed_types_roundtrip(self, tmp_path: Path) -> None:
        """Test round-trip with mixed value types."""
        original = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }
        path = tmp_path / "roundtrip.toon"

        toon_write(path, original)
        parsed = toon_read(path)

        assert parsed == original


class TestJsonToToon:
    """Tests for json_to_toon function."""

    def test_simple_json_conversion(self) -> None:
        """Test converting simple JSON to TOON."""
        json_str = '{"name": "test", "value": 123}'
        toon_result = json_to_toon(json_str)

        assert "name: test" in toon_result
        assert "value: 123" in toon_result

    def test_json_with_lists(self) -> None:
        """Test converting JSON with lists."""
        json_str = '{"items": [1, 2, 3]}'
        toon_result = json_to_toon(json_str)

        assert "items[3]:" in toon_result
        assert "1,2,3" in toon_result

    def test_json_with_nested(self) -> None:
        """Test converting nested JSON."""
        json_str = '{"nested": {"key": "value"}}'
        toon_result = json_to_toon(json_str)

        assert "nested:" in toon_result
        assert "key: value" in toon_result

    def test_json_to_toon_returns_toon_string(self) -> None:
        """Test that json_to_toon returns valid TOON string (not JSON)."""
        original = {"name": "test", "items": [1, 2, 3]}
        json_str = json.dumps(original)

        toon_result = json_to_toon(json_str)

        # TOON format is not valid JSON, so parsing it with json.loads should fail
        # but we can verify it has TOON characteristics
        assert "name: test" in toon_result
        assert "items[3]:" in toon_result


class TestErrorHandling:
    """Tests for error handling."""

    def test_malformed_toon_non_dict(self, tmp_path: Path) -> None:
        """Test that a non-dict top-level structure is handled gracefully."""
        # This is actually valid TOON for a list, but our parser expects dict
        toon_content = "items[2]: 1, 2\n"
        path = tmp_path / "test.toon"
        path.write_text(toon_content)

        # Should return dict with items key
        result = toon_read(path)
        assert "items" in result

    def test_json_to_toon_invalid_json(self) -> None:
        """Test that invalid JSON raises RuntimeError."""
        invalid_json = "{ invalid json }"

        with pytest.raises(RuntimeError):
            json_to_toon(invalid_json)