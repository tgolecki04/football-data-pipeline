
"""Tests for isolated partial pipeline executions."""

import json

import pytest

import run_pipeline

from src.processing.run_context import create_run_directory


@pytest.fixture
def partial_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("LEAGUE_ID", "39")
    monkeypatch.setenv("SEASON", "2023")
    monkeypatch.setenv("COMPETITION_CODE", "PD")

    monkeypatch.setattr(
        run_pipeline,
        "create_run_directory",
        lambda: create_run_directory(base_dir=tmp_path),
    )

    calls = []

    def fake_run_script(script, *args):
        calls.append((script, args))

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        fake_run_script,
    )

    return tmp_path, calls


@pytest.mark.parametrize(
    "mode,source,expected_script,expected_args",
    [
        (
            "ingestion",
            "api_football",
            "src/ingestion/fetch_api_football.py",
            (),
        ),
        (
            "transformation",
            "api_football",
            "src/processing/transform_api_football.py",
            (),
        ),
        (
            "loading",
            "api_football",
            "src/warehouse/load_to_postgres.py",
            ("--source", "api_football"),
        ),
        (
            "loading",
            "football_data",
            "src/warehouse/load_to_postgres.py",
            ("--source", "football_data"),
        ),
        (
            "transformation",
            "football_data",
            "src/processing/transform_football_data.py",
            (),
        ),
        (
            "ingestion",
            "football_data",
            "src/ingestion/fetch_football_data.py",
            (),
        ),
    ],
)
def test_partial_modes_run_only_requested_script(
    partial_environment,
    mode,
    source,
    expected_script,
    expected_args,
):
    tmp_path, calls = partial_environment

    run_pipeline.run_partial_pipeline(mode, source)

    assert calls == [(expected_script, expected_args)]

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]

    report = json.loads(
        (run_dir / "pipeline.json").read_text(encoding="utf-8")
    )

    assert report["status"] == "SUCCESS"
    assert report["source"] == source
    assert report["stages"][mode] == "SUCCESS"
    assert mode in report["stage_durations_seconds"]

    for other in (
        "ingestion",
        "transformation",
        "loading",
        "gold",
        "data_quality",
    ):
        if other != mode:
            assert report["stages"][other] == "NOT_RUN"

    assert (run_dir / "pipeline.log").exists()
    assert not (run_dir / "data_quality.json").exists()

    if source == "football_data":
        assert report["league_id"] == 2014
    else:
        assert report["league_id"] == 39


def test_partial_failure_creates_failed_report(
    partial_environment,
    monkeypatch,
):
    tmp_path, _ = partial_environment

    def fail(*args):
        raise RuntimeError("Synthetic failure")

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        fail,
    )

    with pytest.raises(RuntimeError, match="Synthetic failure"):
        run_pipeline.run_partial_pipeline(
            "transformation",
            "api_football",
        )

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1

    report = json.loads(
        (run_dirs[0] / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "FAILED"
    assert report["stages"]["transformation"] == "FAILED"
    assert report["error"]["stage"] == "transformation"
    assert report["error"]["type"] == "RuntimeError"


@pytest.mark.parametrize("mode", ["unknown", "all", ""])
def test_invalid_partial_mode_creates_no_directory(
    partial_environment,
    mode,
):
    tmp_path, _ = partial_environment

    with pytest.raises(ValueError, match="Unsupported partial mode"):
        run_pipeline.run_partial_pipeline(
            mode,
            "api_football",
        )

    assert list(tmp_path.iterdir()) == []


def test_two_partial_runs_have_distinct_directories(
    partial_environment,
):
    tmp_path, _ = partial_environment

    run_pipeline.run_partial_pipeline(
        "loading", "api_football"
    )
    run_pipeline.run_partial_pipeline(
        "loading", "api_football"
    )

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 2

    assert all(
        (directory / "pipeline.json").exists()
        for directory in run_dirs
    )
