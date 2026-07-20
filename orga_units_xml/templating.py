from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_RE = re.compile(
    r"\$\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}|\$\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}"
)


def _clean_template_value(value: Any, fallback: str = "") -> str:
    return str(fallback if value is None else value).strip()


def render_template_string(value: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        field_name = match.group(1) or match.group(2)
        if field_name not in context:
            raise ValueError(
                f"Unknown template placeholder '{field_name}' in storage location template."
            )
        return _clean_template_value(context[field_name])

    return PLACEHOLDER_RE.sub(replace, value)


def render_template_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return render_template_string(value, context)
    if isinstance(value, list):
        return [render_template_value(item, context) for item in value]
    if isinstance(value, dict):
        return {
            key: render_template_value(item, context) for key, item in value.items()
        }
    return value
