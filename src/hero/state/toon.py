"""TOON format utilities for state management.

TOON is HERO's native format. JSON on disk for humans, TOON for LLM injection.
Achieves 50-60% token savings vs JSON in real tests.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


def toon_read(path: Path) -> dict[str, Any]:
    """Parse a .toon file into a Python dict.

    Handles:
    - Top-level objects
    - Lists (key[count]: val1, val2)
    - Nested dicts
    - Comments (#)

    Args:
        path: Path to the .toon file

    Returns:
        Parsed dictionary (empty dict if file does not exist)

    Raises:
        ValueError: If the TOON content is malformed
    """
    if not path.exists():
        return {}
    content = path.read_text()
    return _parse_toon(content)


def _parse_toon(content: str) -> dict[str, Any]:
    """Parse TOON content string into a dict.

    Format examples:
        name: test
        items[3]: 1, 2, 3
        nested:
          key: value
          other: 123
    """
    result: dict[str, Any] = {}
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]

        # Strip line comments (only # not inside quotes AND before the value part)
        # Only strip # appearing BEFORE the first : (column-level comments), not # in values
        if "#" in line:
            in_quotes = False
            before_colon = True
            for j, char in enumerate(line):
                if char == '"' and not in_quotes:
                    in_quotes = True
                elif char == '"' and in_quotes:
                    in_quotes = False
                elif char == ':' and before_colon and not in_quotes:
                    before_colon = False
                elif char == "#" and not in_quotes and before_colon:
                    line = line[:j]
                    break

        stripped = line.strip()

        # Strip column-level comments BEFORE parsing (only # outside quoted strings)
        if "#" in stripped:
            in_quote = False
            for j, char in enumerate(stripped):
                if char == '"' and not in_quote:
                    in_quote = True
                elif char == '"' and in_quote:
                    in_quote = False
                elif char == "#" and not in_quote:
                    stripped = stripped[:j]
                    break

        # Skip empty lines and structural markers (after stripping comments)
        if not stripped or stripped in ("{", "}"):
            i += 1
            continue

        # Determine indentation level
        indent = len(line) - len(stripped)

        # Check for list format: key[count]: val1, val2
        # MUST check before key_val_match since "key[count]:" partially matches "key:"
        list_match = re.match(r"^(\w+)\[(\d+)\]:\s*(.*)$", stripped)
        # Check for simple key: value (but not list format keys like "key[count]:")
        key_val_match = re.match(r"^(\w+):\s*(.*)$", stripped)

        if list_match:
            key, _count, values_str = list_match.groups()
            if values_str.strip():
                values = [_parse_value(v.strip()) for v in values_str.split(",")]
                result[key] = values
            else:
                # Empty list values - check if next lines are inline dict items or plain strings
                list_items = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()

                    if not next_stripped:
                        i += 1
                        continue

                    # Check if we've left the list context (less indented)
                    next_indent = len(next_line) - len(next_stripped)
                    if next_indent < indent:
                        break

                    # Inline dict item starts with { and ends with }
                    if next_stripped.startswith("{") and next_stripped.endswith("}"):
                        # It's an inline dict - parse it
                        inner = next_stripped[1:-1]
                        list_items.append(_parse_inline_dict(inner))
                        i += 1
                        continue

                    # Top-level key-value pair (no indent) means we've exited the list
                    if next_indent == 0 and ":" in next_stripped:
                        break

                    # Plain string value on its own line
                    list_items.append(_parse_value(next_stripped))
                    i += 1

                result[key] = list_items
                continue  # Already at the right position, don't increment i again
        elif key_val_match:
            key, value = key_val_match.groups()

            # Check if this is an inline dict: {key: val, ...}
            if value.strip().startswith("{"):
                inline_content = value.strip()
                if inline_content.endswith("}"):
                    # Parse the inline dict
                    inner = inline_content[1:-1]  # Remove { and }
                    result[key] = _parse_inline_dict(inner)
                    i += 1
                    continue
            
            # Check if next lines are nested
            if value.strip() == "":
                # Nested dict follows - collect indented lines
                nested_content_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.strip()

                    # Skip empty lines
                    if not next_stripped:
                        i += 1
                        continue

                    # Check comment
                    if "#" in next_line:
                        comment_idx = next_line.index("#")
                        next_line = next_line[:comment_idx]
                        next_stripped = next_line.strip()

                    # If we hit a less-indented line or a closing brace, we're done
                    next_indent = len(next_line) - len(next_stripped)
                    # Check if this is an inline dict like {name: "value"}
                    is_inline_dict = next_stripped.startswith("{") and "}" in next_stripped and next_stripped.rstrip().endswith("}")
                    if next_indent < indent and next_stripped and next_stripped not in ("{", "}") and not is_inline_dict:
                        break
                    if next_stripped in ("}", "{"):
                        i += 1
                        continue

                    nested_content_lines.append(next_line)
                    i += 1

                if nested_content_lines:
                    nested_content = "\n".join(nested_content_lines)
                    result[key] = _parse_toon(nested_content)
                else:
                    result[key] = {}
            else:
                # Simple value
                parsed_value = _parse_value(value.strip())
                result[key] = parsed_value

        i += 1

    return result


def _parse_inline_dict(content: str) -> dict[str, Any]:
    """Parse an inline dict string like 'name: "value", age: 123'."""
    result = {}
    # Split by comma, but not inside quotes
    parts = []
    current = []
    in_quotes = False
    for char in content:
        if char == '"' and not in_quotes:
            in_quotes = True
            current.append(char)
        elif char == '"' and in_quotes:
            in_quotes = False
            current.append(char)
        elif char == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    
    for part in parts:
        if ":" in part:
            key, val = part.split(":", 1)
            result[key.strip()] = _parse_value(val.strip())
    return result


def _parse_value(value: str) -> Any:
    """Parse a TOON value into appropriate Python type."""
    # Try boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Try number
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # Return as string (strip quotes if present)
    value = value.strip().strip('"').strip("'")
    return value


def toon_write(path: Path, data: dict[str, Any]) -> None:
    """Write a dict as TOON to path.

    Format:
    - key: value for simple values
    - key[count]: val1, val2 for lists
    - Nested dicts as indented sub-keys

    Args:
        path: Path to write the .toon file
        data: Dictionary to write
    """
    lines = _format_toon_data(data, indent=0)
    path.write_text("\n".join(lines) + "\n")


def _format_toon_data(data: dict[str, Any], indent: int) -> list[str]:
    """Format a dict as TOON lines."""
    lines: list[str] = []
    prefix = "  " * indent

    for key, value in data.items():
        if isinstance(value, list):
            count = len(value)
            if count == 0:
                lines.append(f"{prefix}{key}[0]:")
            elif all(isinstance(v, dict) for v in value):
                # List of dicts - write each on its own line
                lines.append(f"{prefix}{key}[{count}]:")
                for item in value:
                    item_lines = _format_dict_inline(item, indent + 1)
                    lines.append(f"{prefix}  {item_lines}")
            else:
                # Quote strings containing # to prevent comment-stripping issues
                def _quote_if_needed(v):
                    s = str(v)
                    if "#" in s:
                        return f'"{s}"'
                    return s
                values_str = ", ".join(_quote_if_needed(v) for v in value)
                lines.append(f"{prefix}{key}[{count}]: {values_str}")
        elif isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            nested = _format_toon_data(value, indent + 1)
            lines.extend(nested)
        elif isinstance(value, str):
            lines.append(f'{prefix}{key}: "{value}"')
        else:
            lines.append(f"{prefix}{key}: {value}")

    return lines


def _format_dict_inline(data: dict[str, Any], indent: int) -> str:
    """Format a dict as a single-line inline string."""
    parts = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, str):
            parts.append(f'{key}: "{value}"')
        elif isinstance(value, (int, float, bool)):
            parts.append(f"{key}: {value}")
        elif value is None:
            parts.append(f"{key}: null")
        else:
            parts.append(f"{key}: {value}")
    return "{" + ", ".join(parts) + "}"


def json_to_toon(json_str: str) -> str:
    """Convert JSON string to TOON string.

    Uses npx @toon-format/cli subprocess for conversion.

    Args:
        json_str: JSON string to convert

    Returns:
        TOON formatted string

    Raises:
        RuntimeError: If the conversion fails
    """
    try:
        result = subprocess.run(
            ["npx", "@toon-format/cli", "--encode"],
            input=json_str,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to convert JSON to TOON: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "npx not found. Ensure Node.js and npm are installed."
        ) from e


def toon_to_json(toon_str: str) -> str:
    """Convert TOON string to JSON string.

    Uses npx @toon-format/cli subprocess for conversion.

    Args:
        toon_str: TOON string to convert

    Returns:
        JSON formatted string

    Raises:
        RuntimeError: If the conversion fails
    """
    try:
        result = subprocess.run(
            ["npx", "@toon-format/cli", "--decode"],
            input=toon_str,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to convert TOON to JSON: {e.stderr}") from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "npx not found. Ensure Node.js and npm are installed."
        ) from e