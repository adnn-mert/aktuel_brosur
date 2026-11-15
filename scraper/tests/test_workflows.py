"""The GitHub Actions workflow files parse and keep their safety settings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from scraper.tests.conftest import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"
ALLOWED_ACTIONS = {
    "actions/checkout@v4",
    "actions/setup-python@v5",
    "actions/setup-java@v4",
    "subosito/flutter-action@v2",
}


def load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key "on" as the boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for job in workflow["jobs"].values() for s in job["steps"]]


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name)
def test_every_workflow_parses_and_pins_known_actions(path: Path) -> None:
    workflow = load(path.name)
    assert workflow["name"] and workflow["jobs"]
    assert "permissions" in workflow
    for step in steps(workflow):
        if "uses" in step:
            assert step["uses"] in ALLOWED_ACTIONS, step["uses"]


def test_scrape_workflow() -> None:
    wf = load("scrape.yml")
    assert wf["on"]["schedule"] == [{"cron": "17 3,9,15 * * *"}]
    assert "workflow_dispatch" in wf["on"]
    assert wf["concurrency"] == {"group": "scrape", "cancel-in-progress": False}
    assert wf["permissions"] == {"contents": "write"}
    job = wf["jobs"]["scrape"]
    assert job["timeout-minutes"] == 30
    assert job["env"]["SCRAPER_CONTACT_URL"] == "https://github.com/${{ github.repository }}"
    runs = [s.get("run", "") for s in job["steps"]]
    assert any("fetch-state --dir state" in r for r in runs)
    scrape = next(s for s in job["steps"] if s.get("id") == "scrape")
    # The scraper's exit code must reach the publish step instead of failing the job early.
    assert "set +e" in scrape["run"] and "--state-dir state --out out" in scrape["run"]
    publish = next(s for s in job["steps"] if s.get("id") == "publish")
    assert "${{ steps.scrape.outputs.code }}" in publish["run"] and "scraper.publish publish" in publish["run"]
    # Notifications come last, only after the data went out, and can never fail the job.
    notify = job["steps"][-1]
    assert notify["run"] == "python -m scraper.notify --previous state/catalog.json --current out/catalog.json"
    assert notify["if"] == "${{ !cancelled() && steps.publish.outputs.published == 'true' }}"
    assert notify["continue-on-error"] is True
    assert notify["env"] == {"FIREBASE_SERVICE_ACCOUNT": "${{ secrets.FIREBASE_SERVICE_ACCOUNT }}"}
    assert job["steps"].index(publish) < job["steps"].index(notify)


def test_ci_workflows_are_read_only_and_path_filtered() -> None:
    scraper = load("ci-scraper.yml")
    app = load("ci-app.yml")
    for wf in (scraper, app):
        assert wf["permissions"] == {"contents": "read"}
        assert wf["on"]["push"]["branches"] == ["main"]
        assert wf["on"]["push"]["paths"] == wf["on"]["pull_request"]["paths"]
    assert "scraper/**" in scraper["on"]["push"]["paths"] and "app/**" not in scraper["on"]["push"]["paths"]
    assert app["on"]["push"]["paths"] == ["app/**", ".github/workflows/ci-app.yml"]
    assert any(s.get("run") == "python -m pytest" for s in steps(scraper))
    flutter = next(s for s in steps(app) if s.get("uses", "").startswith("subosito/"))
    assert flutter["with"]["flutter-version"] == "3.47.5" and flutter["with"]["channel"] == "stable"
    assert [s["run"] for s in steps(app) if "run" in s] == ["flutter pub get", "flutter analyze", "flutter test"]


def test_release_workflow() -> None:
    wf = load("release.yml")
    assert wf["on"]["push"] == {"tags": ["v*"]}
    assert wf["on"]["workflow_dispatch"]["inputs"]["tag"]["required"] is True
    assert wf["permissions"] == {"contents": "write"}
    job = wf["jobs"]["release"]
    assert job["env"]["CATALOG_BASE_URL"] == "https://adnn-mert.github.io/aktuel_brosur/"
    # Same Flutter as CI, so a release never builds with an untested toolchain.
    flutter = next(s for s in job["steps"] if s.get("uses", "").startswith("subosito/"))
    assert flutter["with"]["flutter-version"] == "3.47.5" and flutter["with"]["channel"] == "stable"
    # The workflow_dispatch input is untrusted: it may only reach the shell through env.
    for step in job["steps"]:
        assert "inputs." not in step.get("run", ""), step.get("name")
    # The Firebase secret only reaches the step that turns it into dart-defines, via a temp file.
    with_secret = [s for s in job["steps"] if "secrets." in str(s)]
    assert [s["id"] for s in with_secret] == ["defines"]
    defines = with_secret[0]
    assert defines["env"] == {"FIREBASE_GOOGLE_SERVICES_JSON": "${{ secrets.FIREBASE_GOOGLE_SERVICES_JSON }}"}
    assert '"$RUNNER_TEMP/google-services.json"' in defines["run"]
    assert "python3 app/tool/firebase_defines.py" in defines["run"]
    assert "notifications=false" in defines["run"]
    assert "echo $FIREBASE" not in defines["run"] and "cat " not in defines["run"]
    build = next(s for s in job["steps"] if s.get("name") == "Build APK")
    assert '"--dart-define-from-file=$DEFINES"' in build["run"] and "flutter build apk" in build["run"]
    assert "carsi-pazar-$TAG.apk" in build["run"]
    publish = job["steps"][-1]
    assert publish["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert "gh release create" in publish["run"] and "Bilinmeyen kaynaklardan" in publish["run"]
