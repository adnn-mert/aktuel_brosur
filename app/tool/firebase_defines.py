"""Turn a downloaded google-services.json into a dart-define file for the app.

The app does not use the google-services Gradle plugin; it builds FirebaseOptions at runtime
from four --dart-define values (see app/lib/data/notifications.dart). Usage, from the
repository root::

    python app/tool/firebase_defines.py [google-services.json] [-o secrets/firebase_defines.json]
    cd app && flutter run --dart-define-from-file=../secrets/firebase_defines.json

Both files live in the git-ignored ``secrets/`` folder. Other keys already present in the
output file (e.g. CATALOG_BASE_URL) are kept. The values are never printed.

Python standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

PACKAGE_NAME = "dev.aktuelbrosur.aktuel_brosur"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "secrets" / "google-services.json"
DEFAULT_OUTPUT = ROOT / "secrets" / "firebase_defines.json"
KEYS = ("FIREBASE_API_KEY", "FIREBASE_APP_ID", "FIREBASE_MESSAGING_SENDER_ID", "FIREBASE_PROJECT_ID")


class DefinesError(Exception):
    """A problem with the input; the message never contains a key value."""


def _get(data: Any, *path: str | int) -> Any:
    for step in path:
        try:
            data = data[step]
        except (KeyError, IndexError, TypeError):
            return None
    return data


def defines_from_google_services(data: Mapping[str, Any], package_name: str = PACKAGE_NAME) -> dict[str, str]:
    clients = data.get("client") if isinstance(data, Mapping) else None
    if not isinstance(clients, list):
        raise DefinesError("not a google-services.json file (no 'client' list)")
    client = next(
        (c for c in clients if _get(c, "client_info", "android_client_info", "package_name") == package_name),
        None,
    )
    if client is None:
        raise DefinesError(f"no Android app with package {package_name} in this file; add it in the Firebase console")
    values = {
        "FIREBASE_API_KEY": _get(client, "api_key", 0, "current_key"),
        "FIREBASE_APP_ID": _get(client, "client_info", "mobilesdk_app_id"),
        "FIREBASE_MESSAGING_SENDER_ID": _get(data, "project_info", "project_number"),
        "FIREBASE_PROJECT_ID": _get(data, "project_info", "project_id"),
    }
    missing = [k for k, v in values.items() if not isinstance(v, str) or not v.strip()]
    if missing:
        raise DefinesError(f"missing in the file: {', '.join(missing)}")
    return {k: v.strip() for k, v in values.items()}


def write_defines(input_path: Path, output_path: Path) -> list[str]:
    """Writes (or updates) the dart-define file; returns the keys written."""
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DefinesError(f"{input_path} not found; download google-services.json from the Firebase console") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise DefinesError(f"cannot read {input_path}: {type(exc).__name__}") from None
    defines = defines_from_google_services(data)
    existing: dict[str, Any] = {}
    if output_path.is_file():
        try:
            loaded = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            existing = loaded
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({**existing, **defines}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sorted(defines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a dart-define JSON file from google-services.json.")
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT, help=f"default: {DEFAULT_INPUT}")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help=f"default: {DEFAULT_OUTPUT}")
    args = parser.parse_args(argv)
    try:
        keys = write_defines(args.input, args.output)
    except DefinesError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {', '.join(keys)} to {args.output}")
    print(f"run: flutter run --dart-define-from-file={args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
