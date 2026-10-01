from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_RE = re.compile(
    # Support both ${name} and ${{name}} placeholder styles.
    r"\$\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}|\$\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}"
)


def _clean_template_value(value: Any, fallback: str = "") -> str:
    return str(fallback if value is None else value).strip()


def _collect_placeholders(value: Any) -> set[str]:
    # Walk nested template structures and gather referenced placeholder keys.
    if isinstance(value, str):
        return {
            (match.group(1) or match.group(2))
            for match in PLACEHOLDER_RE.finditer(value)
            if (match.group(1) or match.group(2))
        }
    if isinstance(value, list):
        placeholders: set[str] = set()
        for item in value:
            placeholders.update(_collect_placeholders(item))
        return placeholders
    if isinstance(value, dict):
        placeholders = set()
        for item in value.values():
            placeholders.update(_collect_placeholders(item))
        return placeholders
    return set()


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
        # Regular lists are rendered in-place with the same context.
        return [render_template_value(item, context) for item in value]
    if isinstance(value, dict):
        rendered_dict: dict[str, Any] = {}

        for key, item in value.items():
            if key == "sub_locations" and isinstance(item, list):
                context_sub_locations = context.get("sub_locations")
                if isinstance(context_sub_locations, list):
                    # Expand template items against each child sub-location when needed,
                    # so one parent can contain multiple rendered children.
                    rendered_sub_locations: list[Any] = []
                    for template_item in item:
                        placeholders = _collect_placeholders(template_item)
                        missing_placeholders = [
                            placeholder
                            for placeholder in placeholders
                            if placeholder not in context
                        ]

                        # Expand child sub-locations only when unresolved placeholders
                        # can be satisfied from the nested sub-location context.
                        if missing_placeholders and all(
                            any(
                                isinstance(sub_location, dict)
                                and placeholder in sub_location
                                for sub_location in context_sub_locations
                            )
                            for placeholder in missing_placeholders
                        ):
                            for sub_location in context_sub_locations:
                                if not isinstance(sub_location, dict):
                                    continue
                                merged_context = {**context, **sub_location}
                                rendered_sub_locations.append(
                                    render_template_value(template_item, merged_context)
                                )
                        else:
                            rendered_sub_locations.append(
                                render_template_value(template_item, context)
                            )

                    rendered_dict[key] = rendered_sub_locations
                    continue

            rendered_dict[key] = render_template_value(item, context)

        return rendered_dict
    return value
