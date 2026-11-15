"""app/tool/firebase_defines.py: google-services.json -> dart-define file (fake fixture only)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from scraper.tests.conftest import ROOT

_spec = importlib.util.spec_from_file_location("firebase_defines", ROOT / "app" / "tool" / "firebase_defines.py")
assert _spec and _spec.loader
fd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fd)

FAKE_KEY = "AIzaFAKE-not-a-real-key-000000000000000"


def google_services() -> dict[str, Any]:
    """Shape of a real google-services.json with two apps; every value is invented."""

    def client(package: str, app_id: str, key: str) -> dict[str, Any]:
        return {
            "client_info": {"mobilesdk_app_id": app_id, "android_client_info": {"package_name": package}},
            "oauth_client": [],
            "api_key": [{"current_key": key}],
            "services": {"appinvite_service": {"other_platform_oauth_client": []}},
        }

    return {
        "project_info": {"project_number": "123456789012", "project_id": "fake-project", "storage_bucket": "fake.app"},
        "client": [
            client("com.example.other", "1:123456789012:android:other", "AIzaOTHER"),
            client(fd.PACKAGE_NAME, "1:123456789012:android:abcdef", FAKE_KEY),
        ],
        "configuration_version": "1",
    }


def write(path: Path, data: Any) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_picks_the_app_package_and_writes_all_four_defines(tmp_path, capsys) -> None:
    src = write(tmp_path / "google-services.json", google_services())
    out = tmp_path / "secrets" / "firebase_defines.json"
    assert fd.main([str(src), "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {
        "FIREBASE_API_KEY": FAKE_KEY,
        "FIREBASE_APP_ID": "1:123456789012:android:abcdef",
        "FIREBASE_MESSAGING_SENDER_ID": "123456789012",
        "FIREBASE_PROJECT_ID": "fake-project",
    }
    printed = capsys.readouterr()
    assert FAKE_KEY not in printed.out + printed.err
    assert "1:123456789012" not in printed.out + printed.err
    assert "FIREBASE_API_KEY" in printed.out


def test_keeps_other_defines_in_the_output(tmp_path) -> None:
    src = write(tmp_path / "gs.json", google_services())
    out = write(tmp_path / "defines.json", {"CATALOG_BASE_URL": "https://example.test/", "FIREBASE_API_KEY": "old"})
    assert fd.main([str(src), "-o", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["CATALOG_BASE_URL"] == "https://example.test/" and data["FIREBASE_API_KEY"] == FAKE_KEY


def test_default_paths_are_in_the_ignored_secrets_folder() -> None:
    assert fd.DEFAULT_INPUT == ROOT / "secrets" / "google-services.json"
    assert fd.DEFAULT_OUTPUT == ROOT / "secrets" / "firebase_defines.json"
    assert "secrets/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["client"].pop(1), "no Android app with package"),
        (lambda d: d["client"][1].update(api_key=[]), "FIREBASE_API_KEY"),
        (lambda d: d.pop("project_info"), "FIREBASE_MESSAGING_SENDER_ID, FIREBASE_PROJECT_ID"),
        (lambda d: d.pop("client"), "not a google-services.json"),
    ],
)
def test_bad_input_fails_without_printing_values(tmp_path, capsys, mutate, message: str) -> None:
    data = google_services()
    mutate(data)
    out = tmp_path / "out.json"
    assert fd.main([str(write(tmp_path / "gs.json", data)), "-o", str(out)]) == 1
    err = capsys.readouterr().err
    assert message in err and FAKE_KEY not in err
    assert not out.exists()


def test_missing_or_broken_input(tmp_path, capsys) -> None:
    assert fd.main([str(tmp_path / "nope.json"), "-o", str(tmp_path / "o.json")]) == 1
    assert "not found" in capsys.readouterr().err
    broken = tmp_path / "broken.json"
    broken.write_text("{" + FAKE_KEY, encoding="utf-8")
    assert fd.main([str(broken), "-o", str(tmp_path / "o.json")]) == 1
    assert FAKE_KEY not in capsys.readouterr().err
