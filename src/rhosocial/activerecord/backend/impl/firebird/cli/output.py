# src/rhosocial/activerecord/backend/impl/firebird/cli/output.py
"""CLI output formatting utilities."""

from typing import Any, Dict, List, Optional


def format_table(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> str:
    """Format query results as a text table.

    Args:
        rows: List of row dicts
        columns: Column names (auto-detected if None)

    Returns:
        Formatted table string
    """
    if not rows:
        return "(no rows)"

    if columns is None:
        columns = list(rows[0].keys())

    col_widths = {col: len(str(col)) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], len(val))

    sep = "+" + "+".join("-" * (col_widths[c] + 2) for c in columns) + "+"
    header = "|" + "|".join(f" {c:<{col_widths[c]}} " for c in columns) + "|"

    lines = [sep, header, sep]
    for row in rows:
        line = "|" + "|".join(f" {str(row.get(c, '')):<{col_widths[c]}} " for c in columns) + "|"
        lines.append(line)
    lines.append(sep)

    return "\n".join(lines)


def format_json(rows: List[Dict[str, Any]]) -> str:
    """Format query results as JSON."""
    import json
    return json.dumps(rows, indent=2, default=str)


def format_csv(rows: List[Dict[str, Any]]) -> str:
    """Format query results as CSV."""
    if not rows:
        return ""

    columns = list(rows[0].keys())
    lines = [",".join(f'"{c}"' for c in columns)]

    for row in rows:
        values = [str(row.get(c, "")).replace('"', '""') for c in columns]
        lines.append(",".join(f'"{v}"' for v in values))

    return "\n".join(lines)