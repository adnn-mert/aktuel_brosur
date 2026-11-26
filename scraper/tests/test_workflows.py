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
    # issues: write lets scraper.alerts open and close source-failing issues.
    assert wf["permissions"] == {"contents": "write", "issues": "write"}
    job = wf["jobs"]["scrape"]
    # Room for the scrape plus the OCR step's own 55 minutes.
    assert job["timeout-minutes"] == 90
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


def test_scrape_workflow_alerts_step() -> None:
    job = load("scrape.yml")["jobs"]["scrape"]
    publish = next(s for s in job["steps"] if s.get("id") == "publish")
    alerts = next(s for s in job["steps"] if "scraper.alerts" in s.get("run", ""))
    # Right after publishing, and only when the data (and its health.json) went out.
    assert job["steps"].index(alerts) == job["steps"].index(publish) + 1
    assert alerts["run"] == "python -m scraper.alerts --health out/health.json"
    assert alerts["if"] == "${{ !cancelled() && steps.publish.outputs.published == 'true' }}"
    # Alerting can never fail the job, and it gets the repo token, no other secret.
    assert alerts["continue-on-error"] is True
    assert alerts["env"] == {
        "GITHUB_TOKEN": "${{ github.token }}",
        "GITHUB_REPOSITORY": "${{ github.repository }}",
    }
    assert "secrets." not in str(alerts)
    # Only publish (scrape exit 1, git or size failure) can fail the job after scraping.
    assert "continue-on-error" not in publish


def test_scrape_workflow_ocr_step() -> None:
    job = load("scrape.yml")["jobs"]["scrape"]
    order = [s.get("id") or s.get("name") for s in job["steps"]]
    ocr = next(s for s in job["steps"] if "scraper ocr" in s.get("run", ""))
    # Between scraping (which writes out/) and publishing (which ships it).
    assert order.index("scrape") + 1 == job["steps"].index(ocr) == order.index("publish") - 1
    assert ocr["run"] == "python -m scraper ocr --state-dir state --out out"
    # Only when the scrape wrote out/ (the same exit codes the publish step publishes on).
    assert ocr["if"] == "${{ steps.scrape.outputs.code == '0' || steps.scrape.outputs.code == '2' }}"
    # It can never fail the job, and its timeout stays inside the job's while leaving the
    # code's 50-minute time budget (scraper.ocr.pipeline.TIME_BUDGET) room to finish.
    assert ocr["continue-on-error"] is True
    assert 50 < ocr["timeout-minutes"] < job["timeout-minutes"]
    # The key reaches this step only, through an exact env mapping.
    assert ocr["env"] == {"GEMINI_API_KEY": "${{ secrets.GEMINI_API_KEY }}"}
    assert [s.get("name") for s in job["steps"] if "GEMINI" in str(s)] == [ocr["name"]]
    assert "GEMINI" not in str(job.get("env", {}))
    assert "echo" not in ocr["run"] and "cat " not in ocr["run"]


def test_scrape_workflow_ocr_timeout_matches_the_code_budget() -> None:
    from scraper.ocr.pipeline import TIME_BUDGET

    ocr = next(s for s in load("scrape.yml")["jobs"]["scrape"]["steps"] if "scraper ocr" in s.get("run", ""))
    assert TIME_BUDGET < ocr["timeout-minutes"] * 60


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
    by_name = {s["name"]: s for s in job["steps"] if "name" in s}
    # Each secret reaches only the steps that need it, each with an exact env mapping; no other
    # step may mention a secret, so none can print one by accident.
    def reaching(secret: str) -> list[str | None]:
        return [s.get("name") for s in job["steps"] if f"secrets.{secret}" in str(s)]

    assert reaching("FIREBASE_GOOGLE_SERVICES_JSON") == ["Write dart-define file"]
    assert reaching("ANDROID_KEYSTORE_BASE64") == ["Restore the release signing key"]
    for secret in ("ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD"):
        assert reaching(secret) == ["Restore the release signing key", "Build APKs"], secret
    assert [s.get("name") for s in job["steps"] if "secrets." in str(s)] == [
        "Restore the release signing key",
        "Write dart-define file",
        "Build APKs",
    ]
    # The Firebase secret only reaches the step that turns it into dart-defines, via a temp file.
    defines = by_name["Write dart-define file"]
    assert defines["id"] == "defines"
    assert defines["env"] == {"FIREBASE_GOOGLE_SERVICES_JSON": "${{ secrets.FIREBASE_GOOGLE_SERVICES_JSON }}"}
    assert '"$RUNNER_TEMP/google-services.json"' in defines["run"]
    assert "python3 app/tool/firebase_defines.py" in defines["run"]
    assert "notifications=false" in defines["run"]
    assert "echo $FIREBASE" not in defines["run"] and "cat " not in defines["run"]
    # The release key: all four secrets only in the restore step; the build gets everything except
    # the base64 keystore (it reads the decoded file through ANDROID_KEYSTORE_PATH).
    restore = by_name["Restore the release signing key"]
    assert restore["env"] == {
        "ANDROID_KEYSTORE_BASE64": "${{ secrets.ANDROID_KEYSTORE_BASE64 }}",
        "ANDROID_KEYSTORE_PASSWORD": "${{ secrets.ANDROID_KEYSTORE_PASSWORD }}",
        "ANDROID_KEY_ALIAS": "${{ secrets.ANDROID_KEY_ALIAS }}",
        "ANDROID_KEY_PASSWORD": "${{ secrets.ANDROID_KEY_PASSWORD }}",
    }
    script = restore["run"]
    assert "exit 1" in script and "Missing repository secrets" in script
    assert '"$RUNNER_TEMP/release.jks"' in script
    assert 'base64 --decode > "$keystore"' in script
    # Only the path is exported; no secret is echoed, cat-ed or written to GITHUB_ENV/OUTPUT.
    assert script.count("GITHUB_ENV") == 1
    assert 'echo "ANDROID_KEYSTORE_PATH=$keystore" >> "$GITHUB_ENV"' in script
    assert "GITHUB_OUTPUT" not in script and "cat " not in script
    for secret in restore["env"]:
        assert f"echo ${secret}" not in script and f'echo "${secret}' not in script
        assert f"${{{secret}" not in script.replace("${!name}", "")
    build = by_name["Build APKs"]
    assert build["env"] == {
        "DEFINES": "${{ steps.defines.outputs.file }}",
        "BUILD_NUMBER": "${{ github.run_number }}",
        "ANDROID_KEYSTORE_PASSWORD": "${{ secrets.ANDROID_KEYSTORE_PASSWORD }}",
        "ANDROID_KEY_ALIAS": "${{ secrets.ANDROID_KEY_ALIAS }}",
        "ANDROID_KEY_PASSWORD": "${{ secrets.ANDROID_KEY_PASSWORD }}",
    }
    assert "ANDROID_KEYSTORE_BASE64" not in str(build)
    assert '"--dart-define-from-file=$DEFINES"' in build["run"] and "flutter build apk" in build["run"]
    assert "--split-per-abi" in build["run"]
    for abi in ("arm64", "armv7", "x86_64"):
        assert f'"$RUNNER_TEMP/dist/carsi-pazar-$TAG-{abi}.apk"' in build["run"]
    assert "carsi-pazar-$TAG.apk" not in build["run"]
    assert 'rm -f "$DEFINES" "$ANDROID_KEYSTORE_PATH"' in build["run"]
    # The signing check runs after the build and before publishing; a debug certificate fails it.
    check = by_name["Check the APK signature"]
    assert "secrets." not in str(check)
    assert "apksigner" in check["run"] and "verify --print-certs" in check["run"]
    assert "Android Debug" in check["run"] and "exit 1" in check["run"]
    order = [s.get("name") for s in job["steps"]]
    assert order.index("Restore the release signing key") < order.index("Build APKs")
    assert order.index("Build APKs") < order.index("Check the APK signature") < len(order) - 1
    publish = job["steps"][-1]
    assert publish["env"]["GH_TOKEN"] == "${{ github.token }}"
    assert publish["env"].keys() == {"GH_TOKEN", "NOTIFICATIONS"}
    assert 'apks=("$RUNNER_TEMP"/dist/*.apk)' in publish["run"]
    assert 'gh release create "$TAG" "${apks[@]}"' in publish["run"]
    assert 'gh release upload "$TAG" "${apks[@]}"' in publish["run"]
    assert "Bilinmeyen kaynaklardan" in publish["run"]
