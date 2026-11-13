"""Schema and consistency checks for the published JSON files.

Nothing is published unless it passes these checks, so every message names the
offending field (``brochures[3].pages``) and says why it was rejected.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema import ValidationError as SchemaError
from jsonschema.validators import extend

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"


class ContractError(ValueError):
    """Raised when a document breaks the JSON contract; ``errors`` lists every problem."""

    def __init__(self, document: str, errors: list[str]) -> None:
        self.document = document
        self.errors = errors
        lines = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"{document} is invalid ({len(errors)} problem(s)):\n{lines}")


def _is_strict_int(_checker: Any, instance: Any) -> bool:
    # JSON Schema counts 3.0 as an integer, but Dart's jsonDecode turns it into a double
    # and an `as int` cast in the app would throw, so floats are rejected outright.
    return isinstance(instance, int) and not isinstance(instance, bool)


_StrictValidator = extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_strict_int),
)

_format_checker = FormatChecker()


# jsonschema only checks "date-time" when an optional extra package is installed;
# the stdlib parser is enough here because the schema pattern already pins the shape.
@_format_checker.checks("date-time", raises=ValueError)
def _check_date_time(value: object) -> bool:
    if isinstance(value, str):
        datetime.fromisoformat(value)
    return True


@_format_checker.checks("date", raises=ValueError)
def _check_date(value: object) -> bool:
    if isinstance(value, str):
        date.fromisoformat(value)
    return True


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Load ``schema/<name>.schema.json``."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return _StrictValidator(schema, format_checker=_format_checker)


def validate_catalog(data: Any) -> None:
    _run("catalog", data, _catalog_consistency)


def validate_products(data: Any) -> None:
    _run("products", data, None)


def validate_health(data: Any) -> None:
    _run("health", data, _health_consistency)


def _run(name: str, data: Any, consistency) -> None:
    found = [leaf for top in _validator(name).iter_errors(data) for leaf in _expand(top)]
    errors = [_format_schema_error(e, data) for e in _sorted(found)]
    # Cross-record rules assume a structurally valid document, so they only run after it.
    if not errors and consistency is not None:
        errors = list(consistency(data))
    if errors:
        raise ContractError(name, errors)


def _expand(error: SchemaError) -> list[SchemaError]:
    """Replace a failed "X or null" anyOf by the errors inside X.

    Otherwise a bad ``cover.url`` would only be reported as "cover matches nothing",
    which hides the field that is actually wrong.
    """
    if error.validator not in ("anyOf", "oneOf") or not error.context:
        return [error]
    branches: dict[Any, list[SchemaError]] = {}
    for sub in error.context:
        branches.setdefault(sub.relative_schema_path[0], []).append(sub)
    real = [
        errs
        for errs in branches.values()
        if not (len(errs) == 1 and errs[0].validator == "type" and errs[0].validator_value == "null")
    ]
    if len(real) != 1:
        return [error]
    return [leaf for sub in real[0] for leaf in _expand(sub)]


def _sorted(errors: Iterable[SchemaError]) -> list[SchemaError]:
    return sorted(errors, key=lambda e: [str(p) for p in e.absolute_path])


def _json_path(path: Iterable[Any]) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "<root>"


def _format_schema_error(error: SchemaError, data: Any) -> str:
    path = list(error.absolute_path)
    where = _json_path(path)
    record = _record_hint(data, path)
    # "required" errors point at the parent object; name the missing key instead.
    if error.validator == "required":
        missing = error.message.split("'")[1] if "'" in error.message else error.message
        where = _json_path([*path, missing])
        return f"{where}{record}: required field is missing"
    message = _short_message(error)
    # Errors from the if/then rules only make sense together with the brochure kind.
    if "then" in error.absolute_schema_path and len(path) >= 2:
        try:
            kind = data[path[0]][path[1]].get("kind")
        except (KeyError, IndexError, TypeError, AttributeError):
            kind = None
        if kind is not None:
            message += f" (required when kind is {kind!r})"
    return f"{where}{record}: {message}"


def _short_message(error: SchemaError) -> str:
    if error.validator in ("anyOf", "oneOf"):
        return f"{error.instance!r} matches none of: " + "; ".join(_alternatives(error))
    if error.validator == "pattern" and isinstance(error.schema, dict) and error.schema.get("description"):
        return f"{error.instance!r} is not allowed, expected: {error.schema['description']}"
    return error.message


def _alternatives(error: SchemaError) -> list[str]:
    """Describe each rejected branch of an anyOf, e.g. "Absolute https URL; null"."""
    hints: list[str] = []
    for sub in error.context or ():
        if sub.validator in ("anyOf", "oneOf"):
            found = _alternatives(sub)
        elif sub.validator == "type" and sub.validator_value == "null":
            found = ["null"]
        elif isinstance(sub.schema, dict) and sub.schema.get("description"):
            found = [str(sub.schema["description"]).rstrip(".")]
        else:
            found = [sub.message]
        hints.extend(h for h in found if h not in hints)
    return hints


def _record_hint(data: Any, path: list[Any]) -> str:
    """Add the record id, e.g. ``brochures[3] (id=sok-...)``, so errors are easy to locate."""
    if len(path) >= 2 and path[0] in ("chains", "brochures", "sources") and isinstance(path[1], int):
        try:
            record = data[path[0]][path[1]]
        except (KeyError, IndexError, TypeError):
            return ""
        key = "chain_id" if path[0] == "sources" else "id"
        if isinstance(record, dict) and isinstance(record.get(key), str):
            return f" ({key}={record[key]})"
    return ""


def _catalog_consistency(data: dict[str, Any]) -> Iterator[str]:
    chains: dict[str, dict[str, Any]] = {}
    for i, chain in enumerate(data["chains"]):
        if chain["id"] in chains:
            yield f"chains[{i}].id: duplicate chain id {chain['id']!r}"
        chains.setdefault(chain["id"], chain)

    seen: dict[str, int] = {}
    for i, b in enumerate(data["brochures"]):
        at = f"brochures[{i}]"
        hint = f" (id={b['id']})"
        if b["id"] in seen:
            yield f"{at}.id{hint}: duplicate brochure id (first used by brochures[{seen[b['id']]}])"
        else:
            seen[b["id"]] = i

        chain = chains.get(b["chain_id"])
        if chain is None:
            yield f"{at}.chain_id{hint}: unknown chain {b['chain_id']!r} (not listed in chains)"
        elif chain["kind"] == "webview":
            yield f"{at}.chain_id{hint}: chain {b['chain_id']!r} is kind 'webview' and must not have brochures"

        if b["valid_from"] and b["valid_to"] and b["valid_from"] > b["valid_to"]:
            yield f"{at}.valid_from{hint}: {b['valid_from']} is after valid_to {b['valid_to']}"


def _health_consistency(data: dict[str, Any]) -> Iterator[str]:
    seen: set[str] = set()
    for i, s in enumerate(data["sources"]):
        at = f"sources[{i}]"
        hint = f" (chain_id={s['chain_id']})"
        if s["chain_id"] in seen:
            yield f"{at}.chain_id{hint}: duplicate source"
        seen.add(s["chain_id"])
        if s["ok"] and s["consecutive_failures"] != 0:
            yield f"{at}.consecutive_failures{hint}: must be 0 when ok is true"
        if not s["ok"] and not s["last_error"]:
            yield f"{at}.last_error{hint}: must explain the failure when ok is false"
