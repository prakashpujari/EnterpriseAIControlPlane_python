"""
Robust JSON extraction from LLM text outputs.

LLMs frequently wrap JSON in markdown code fences, prepend explanatory
prose, or append trailing commentary. Naive ``json.loads`` then raises
``json.JSONDecodeError`` ("Extra data", "Expecting value", etc.).

``extract_json`` tolerates all of these and returns ``default`` when no
valid JSON object/array can be found.
"""

import json
import re
from typing import Any

_BRACE_RE = re.compile(r'[{\[]')


def extract_json(text: str, default: Any = None) -> Any:
    """
    Extract a JSON object or array from arbitrary LLM text.

    Handles:
    - empty / whitespace-only input -> returns ``default``
    - markdown code fences (```json ... ``` or ``` ... ```)
    - leading or trailing prose around the JSON
    - bare JSON values (strings/numbers) are returned as-is

    Args:
        text: Raw model output.
        default: Value returned when no valid JSON is found.

    Returns:
        Parsed Python object, or ``default``.
    """
    if not text or not text.strip():
        return default

    candidate = text.strip()

    # Strip a single markdown code fence if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
    if fence:
        candidate = fence.group(1).strip()

    # Fast path: the whole (possibly fenced) string is valid JSON.
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass

    # Otherwise scan for the first balanced object/array. raw_decode
    # tolerates trailing prose after the JSON value.
    decoder = json.JSONDecoder()
    for match in _BRACE_RE.finditer(candidate):
        try:
            obj, _ = decoder.raw_decode(candidate[match.start():])
            return obj
        except (json.JSONDecodeError, ValueError):
            continue

    return default


def is_valid_json(text: str) -> bool:
    """Return True if ``text`` contains at least one parseable JSON value."""
    return extract_json(text, _SENTINEL) is not _SENTINEL


_SENTINEL = object()
