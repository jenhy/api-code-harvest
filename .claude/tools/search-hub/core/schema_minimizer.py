"""JSON Schema minimizer — aggressively reduce MCP tool token consumption.

Firecrawl tool schemas have deeply nested properties with paragraph-length descriptions.
This module walks the schema tree and strips non-essential verbosity.

Three levels (configurable via schema_minimization.mode in config.yaml):
  - 'standard': truncate descriptions to 60 chars, remove titles/examples
  - 'compact': truncate descriptions to 30 chars, remove titles/examples/defaults/constraints
  - 'minimal': remove ALL descriptions from nested properties (keep top-level only),
               remove titles/examples/defaults/constraints/format
"""

import copy
from typing import Any

# Top-level schema keys that MUST be preserved for correct MCP tool registration
_STRUCTURAL_KEYS = {
    "type",
    "properties",
    "items",
    "required",
    "enum",
    "anyOf",
    "oneOf",
    "additionalProperties",
    "const",
    "prefixItems",
}

# Keys that provide minor hints but cost tokens — dropped in 'compact' mode
_CONSTRAINT_KEYS = {
    "pattern",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "default",
    "format",
}

# Keys that are purely meta — always dropped
_VERBOSE_KEYS = {"title", "examples", "$schema", "$id", "$comment", "markdownDescription"}


def minimize_tool_schema(
    schema: dict,
    max_desc: int = 30,
    strip_nested_descriptions: bool = False,
    keep_constraints: bool = False,
) -> dict:
    """Minimize a tool's inputSchema to reduce token usage.

    Args:
        schema: The JSON Schema dict to minimize.
        max_desc: Max characters for any description (0 = remove all descriptions).
        strip_nested_descriptions: If True, only keep descriptions at the
            top-level tool properties (remove descriptions from nested objects).
        keep_constraints: If True, preserve default/min/max/pattern/format keys.
    """
    if not isinstance(schema, dict):
        return schema
    return _minimize(
        schema, max_desc=max_desc, depth=0,
        strip_nested=strip_nested_descriptions,
        keep_constraints=keep_constraints,
    )


def _minimize(
    node: Any,
    max_desc: int,
    depth: int,
    strip_nested: bool,
    keep_constraints: bool,
) -> Any:
    """Recursively minimize a schema node."""
    if not isinstance(node, dict):
        return node

    result: dict[str, Any] = {}

    for key, value in node.items():
        # --- Handle descriptions ---
        if key in ("description", "markdownDescription"):
            if not isinstance(value, str) or not value.strip():
                continue
            if strip_nested and depth > 1:
                # Only keep descriptions at top-level and direct child properties
                continue
            if max_desc == 0:
                continue
            short = value.strip()[:max_desc].strip()
            # Try to break at sentence boundary
            for delim in (". ", "!\n", "?\n", ".\n", "！", "。", "\n"):
                idx = short.rfind(delim)
                if idx > 6:
                    short = short[: idx + 1]
                    break
            result["description"] = short

        # --- Recurse into properties (always structural) ---
        elif key == "properties":
            result[key] = {
                k: _minimize(v, max_desc, depth + 1, strip_nested, keep_constraints)
                for k, v in value.items()
            }

        # --- Keep structural keys (type, required, enum, etc.) ---
        elif key in _STRUCTURAL_KEYS:
            result[key] = _minimize(
                value, max_desc, depth + 1 if key == "items" else depth,
                strip_nested, keep_constraints,
            )

        # --- Constraint keys (optional, dropped in compact mode) ---
        elif key in _CONSTRAINT_KEYS:
            if keep_constraints:
                result[key] = value

        # --- Drop verbose-only keys ---
        elif key in _VERBOSE_KEYS:
            continue

        # --- Pass through unknown keys ---
        else:
            result[key] = _minimize(
                value, max_desc, depth + 1, strip_nested, keep_constraints,
            )

    return result


# --- Convenience presets ---

def standard(schema: dict) -> dict:
    """Remove titles/examples, truncate descriptions to 60 chars."""
    return minimize_tool_schema(schema, max_desc=60, strip_nested_descriptions=False, keep_constraints=True)


def compact(schema: dict) -> dict:
    """More aggressive: 30-char descriptions, drop constraints/defaults."""
    return minimize_tool_schema(schema, max_desc=30, strip_nested_descriptions=False, keep_constraints=False)


def minimal(schema: dict) -> dict:
    """Maximum savings: only top-level descriptions, no constraints."""
    return minimize_tool_schema(schema, max_desc=30, strip_nested_descriptions=True, keep_constraints=False)
