"""Command line entry point: ``python -m scraper <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from scraper.core.validate import ContractError, validate_catalog, validate_health, validate_products

_VALIDATORS = {
    "catalog": validate_catalog,
    "products": validate_products,
    "health": validate_health,
}

EXIT_INVALID = 1
EXIT_USAGE = 2


def _cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except json.JSONDecodeError as exc:
        print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_INVALID
    try:
        _VALIDATORS[args.type](data)
    except ContractError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"{path}: valid {args.type}")
    return 0


def _cmd_probe(_args: argparse.Namespace) -> int:
    from scraper import probe

    return probe.main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m scraper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="check a JSON file against its schema and consistency rules")
    p_validate.add_argument("file", help="path to the JSON file (catalog.json by default)")
    p_validate.add_argument(
        "--type",
        choices=sorted(_VALIDATORS),
        default="catalog",
        help="which contract the file follows (default: catalog)",
    )
    p_validate.set_defaults(func=_cmd_validate)

    p_probe = sub.add_parser("probe", help="send one request to every source and print a reachability table")
    p_probe.set_defaults(func=_cmd_probe)

    from scraper import runner

    p_run = sub.add_parser(
        "run",
        help="scrape the sources and publish catalog.json, health.json, products/ and media/",
        description="Exit codes: 0 published; 2 published but a source failed 3+ times in a row; 1 not published.",
    )
    runner.add_arguments(p_run)
    p_run.set_defaults(func=runner.main)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; Turkish text must not crash output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
