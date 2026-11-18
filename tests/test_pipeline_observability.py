
"""Integration-style tests for orchestration and run artifacts.

No Docker, PostgreSQL or RustFS required.
"""

import json

import pytest

import run_pipeline

from src.processing.data_quality_report import (
    generate_data_quality_report,
)
from src.processing.run_context import create_run_directory


@pytest.fixture
def isolated_pipeline(monkeypatch, tmp_path):
    """Replace external pipeline stages with safe test doubles."""

    monkeypatch.setenv("LEAGUE_ID", "39")
    monkeypatch.setenv("SEASON", "2023")

    monkeypatch.setattr(
        run_pipeline,
        "create_run_directory",
        lambda: create_run_directory(base_dir=tmp_path),
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        lambda script, *args: None,
    )

    monkeypatch.setattr(
        run_pipeline,
        "create_gold_view",
        lambda: None,
    )

    def fake_quality_checks(**kwargs):
        return generate_data_quality_report(
            [
                {
                    "name": "duplicate_fixture_ids",
                    "status": "PASS",
                    "failures": 0,
                }
            ],
            run_id=kwargs["run_id"],
            run_dir=kwargs["run_dir"],
            source=kwargs["source"],
        )

    monkeypatch.setattr(
        run_pipeline,
        "run_data_quality_checks",
        fake_quality_checks,
    )

    return tmp_path


def test_successful_run_writes_all_artifacts(isolated_pipeline):
    run_pipeline.run_for_season(
        fetch=False,
        source="api_football",
    )

    directories = list(isolated_pipeline.iterdir())

    assert len(directories) == 1

    run_dir = directories[0]

    assert (run_dir / "pipeline.json").exists()
    assert (run_dir / "data_quality.json").exists()
    assert (run_dir / "pipeline.log").exists()

    pipeline = json.loads(
        (run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    quality = json.loads(
        (run_dir / "data_quality.json").read_text(
            encoding="utf-8"
        )
    )

    assert pipeline["status"] == "SUCCESS"
    assert pipeline["source"] == "api_football"
    assert pipeline["run_id"] == quality["run_id"]
    assert pipeline["stages"]["loading"] == "SUCCESS"

    assert "loading" in pipeline["stage_durations_seconds"]


def test_two_runs_do_not_overwrite_each_other(
    isolated_pipeline,
):
    run_pipeline.run_for_season(
        fetch=False,
        source="api_football",
    )

    run_pipeline.run_for_season(
        fetch=False,
        source="api_football",
    )

    directories = list(isolated_pipeline.iterdir())

    assert len(directories) == 2

    for directory in directories:
        assert (directory / "pipeline.json").exists()


def test_failed_run_still_writes_report(
    isolated_pipeline,
    monkeypatch,
):
    def failing_script(script, *args):
        if "transform_api_football.py" in script:
            raise RuntimeError("Synthetic transform failure")

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        failing_script,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic transform failure",
    ):
        run_pipeline.run_for_season(
            fetch=False,
            source="api_football",
        )

    directories = list(isolated_pipeline.iterdir())

    assert len(directories) == 1

    run_dir = directories[0]

    pipeline = json.loads(
        (run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert pipeline["status"] == "FAILED"
    assert pipeline["stages"]["transformation"] == "FAILED"
    assert pipeline["error"]["stage"] == "transformation"
    assert pipeline["error"]["type"] == "RuntimeError"
    assert "transformation" in pipeline[
        "stage_durations_seconds"
    ]

    assert (run_dir / "pipeline.log").exists()


def test_successful_pipeline_fails_if_report_cannot_be_saved(
    isolated_pipeline,
    monkeypatch,
):
    """A missing execution report must not be silently ignored."""

    def fail_report(*args, **kwargs):
        raise OSError("Synthetic report write failure")

    monkeypatch.setattr(
        run_pipeline,
        "generate_pipeline_report",
        fail_report,
    )

    with pytest.raises(
        OSError,
        match="Synthetic report write failure",
    ):
        run_pipeline.run_for_season(
            fetch=False,
            source="api_football",
        )

    run_dirs = list(isolated_pipeline.iterdir())

    assert len(run_dirs) == 1

    run_dir = run_dirs[0]

    assert (run_dir / "pipeline.log").exists()
    assert not (run_dir / "pipeline.json").exists()

    # The run-specific logging handler must have been closed.
    assert not any(
        getattr(handler, "baseFilename", None)
        == str(run_dir / "pipeline.log")
        for handler in run_pipeline.logging.getLogger().handlers
    )
