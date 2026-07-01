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


def create_provider(output_format: str, ascii_borders: bool = False):
    """Factory function to get the correct output provider."""
    from rhosocial.activerecord.backend.output import (
        JsonOutputProvider, CsvOutputProvider, TsvOutputProvider
    )

    try:
        from rhosocial.activerecord.backend.output_rich import RichOutputProvider
        rich_available = True
    except ImportError:
        rich_available = False
        RichOutputProvider = None

    if output_format == "table" and not rich_available:
        output_format = "json"

    if output_format == "table" and rich_available:
        from rich.console import Console
        return RichOutputProvider(console=Console(), ascii_borders=ascii_borders)
    if output_format == "json":
        return JsonOutputProvider()
    if output_format == "csv":
        return CsvOutputProvider()
    if output_format == "tsv":
        return TsvOutputProvider()

    return JsonOutputProvider()