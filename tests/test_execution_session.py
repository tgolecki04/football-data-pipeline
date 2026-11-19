
import json

import pytest

from src.processing.execution_session import ExecutionSession


def test_one_session_contains_multiple_seasons(tmp_path):
    session = ExecutionSession.create(
        source="api_football",
        mode="full",
        base_dir=tmp_path,
    )

    for season in (2022, 2023, 2024):
        session.seasons.append({
            "league_id": 39,
            "season": season,
            "status": "SUCCESS",
            "stages": {"loading": "SUCCESS"},
        })

    session.save_reports()

    directories = list(tmp_path.iterdir())

    assert len(directories) == 1
    assert directories[0] == session.run_dir

    report = json.loads(
        (session.run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "SUCCESS"
    assert len(report["seasons"]) == 3
    assert [
        item["season"] for item in report["seasons"]
    ] == [2022, 2023, 2024]


def test_failed_season_fails_whole_session(tmp_path):
    session = ExecutionSession.create(
        source="api_football",
        mode="full",
        base_dir=tmp_path,
    )

    session.seasons.extend([
        {"season": 2022, "status": "SUCCESS"},
        {"season": 2023, "status": "FAILED"},
    ])

    session.save_reports()

    report = json.loads(
        (session.run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "FAILED"


def test_quality_results_are_aggregated(tmp_path):
    session = ExecutionSession.create(
        source="api_football",
        mode="full",
        base_dir=tmp_path,
    )

    for season in (2022, 2023):
        session.quality_results.append({
            "season": season,
            "total_checks": 4,
            "failed_checks": 0,
            "overall_status": "PASS",
            "checks": [],
        })

    session.save_reports()

    report = json.loads(
        (session.run_dir / "data_quality.json").read_text(
            encoding="utf-8"
        )
    )

    assert len(report["seasons"]) == 2
    assert report["total_checks"] == 8
    assert report["failed_checks"] == 0


def test_partial_run_has_no_quality_file(tmp_path):
    session = ExecutionSession.create(
        source="api_football",
        mode="loading",
        base_dir=tmp_path,
    )

    session.seasons.append({
        "season": 2023,
        "status": "SUCCESS",
    })

    session.save_reports()

    assert (session.run_dir / "pipeline.json").exists()
    assert not (session.run_dir / "data_quality.json").exists()
    

def test_cli_three_seasons_use_one_run_directory(
    tmp_path,
    monkeypatch,
):
    import run_pipeline

    monkeypatch.setattr(
        run_pipeline.ExecutionSession,
        "create",
        classmethod(
            lambda cls, source, mode: cls.create_for_test(
                source, mode, tmp_path
            )
        ),
    )

    # Test-only factory to avoid writing real artifacts.
    monkeypatch.setattr(
        run_pipeline.ExecutionSession,
        "create_for_test",
        classmethod(
            lambda cls, source, mode, directory: cls(
                run_id="test_execution",
                run_dir=directory / "test_execution",
                source=source,
                mode=mode,
            )
        ),
        raising=False,
    )

    def fake_season(fetch, source, session):
        session.seasons.append({
            "league_id": 39,
            "season": int(run_pipeline.os.environ["SEASON"]),
            "status": "SUCCESS",
            "stages": {"loading": "SUCCESS"},
        })

    monkeypatch.setattr(
        run_pipeline,
        "run_for_season",
        fake_season,
    )

    monkeypatch.setattr(
        run_pipeline.sys,
        "argv",
        [
            "run_pipeline.py",
            "--source", "api_football",
            "--league-id", "39",
            "--season", "2022", "2023", "2024",
        ],
    )

    monkeypatch.setattr(
        run_pipeline,
        "create_run_log_handler",
        lambda directory: _create_test_handler(directory),
    )

    run_pipeline.main()

    directories = list(tmp_path.iterdir())
    assert len(directories) == 1

    report = json.loads(
        (
            directories[0] / "pipeline.json"
        ).read_text(encoding="utf-8")
    )

    assert len(report["seasons"]) == 3


def _create_test_handler(directory):
    import logging

    directory.mkdir(parents=True, exist_ok=True)

    return logging.FileHandler(
        directory / "pipeline.log",
        encoding="utf-8",
    )
    

def test_cli_failure_in_second_season_keeps_one_run(
    tmp_path,
    monkeypatch,
):
    import json
    import run_pipeline

    original_create = run_pipeline.ExecutionSession.create

    def create_test_session(cls, source, mode):
        return original_create(
            source=source,
            mode=mode,
            base_dir=tmp_path,
        )

    monkeypatch.setattr(
        run_pipeline.ExecutionSession,
        "create",
        classmethod(create_test_session),
    )

    executed_seasons = []

    def fake_run_for_season(fetch, source, session):
        season = int(run_pipeline.os.environ["SEASON"])
        executed_seasons.append(season)

        status = "FAILED" if season == 2023 else "SUCCESS"

        session.seasons.append({
            "league_id": 39,
            "season": season,
            "status": status,
            "stages": {
                "loading": status,
            },
        })

        if season == 2023:
            raise RuntimeError("Synthetic failure in season 2023")

    monkeypatch.setattr(
        run_pipeline,
        "run_for_season",
        fake_run_for_season,
    )

    monkeypatch.setattr(
        run_pipeline.sys,
        "argv",
        [
            "run_pipeline.py",
            "--source", "api_football",
            "--league-id", "39",
            "--season", "2022", "2023", "2024",
        ],
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic failure in season 2023",
    ):
        run_pipeline.main()

    run_dirs = [
        path for path in tmp_path.iterdir()
        if path.is_dir()
    ]

    assert len(run_dirs) == 1

    run_dir = run_dirs[0]

    assert (run_dir / "pipeline.json").exists()
    assert (run_dir / "pipeline.log").exists()

    report = json.loads(
        (run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["status"] == "FAILED"
    assert executed_seasons == [2022, 2023]

    assert [
        item["season"] for item in report["seasons"]
    ] == [2022, 2023]

    assert [
        item["status"] for item in report["seasons"]
    ] == ["SUCCESS", "FAILED"]


def test_failed_data_quality_is_preserved_in_session(
    tmp_path,
    monkeypatch,
):
    import json
    import run_pipeline

    session = ExecutionSession.create(
        source="api_football",
        mode="full",
        base_dir=tmp_path,
    )

    monkeypatch.setenv("LEAGUE_ID", "39")
    monkeypatch.setenv("SEASON", "2023")

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        lambda *args: None,
    )
    monkeypatch.setattr(
        run_pipeline,
        "create_gold_view",
        lambda: None,
    )

    def fake_data_quality_checks(
        *,
        run_id=None,
        run_dir=None,
        source=None,
        on_report=None,
    ):
        report = {
            "overall_status": "FAIL",
            "total_checks": 2,
            "failed_checks": 1,
            "checks": [
                {
                    "name": "duplicate_fixture_ids",
                    "status": "PASS",
                    "failures": 0,
                },
                {
                    "name": "invalid_finished_fixtures",
                    "status": "FAIL",
                    "failures": 1,
                },
            ],
        }

        if on_report is not None:
            on_report(report)

        raise ValueError("Synthetic Data Quality failure")

    monkeypatch.setattr(
        run_pipeline,
        "run_data_quality_checks",
        fake_data_quality_checks,
    )

    with pytest.raises(
        ValueError,
        match="Synthetic Data Quality failure",
    ):
        run_pipeline.run_for_season(
            fetch=False,
            source="api_football",
            session=session,
        )

    session.save_reports()

    pipeline_report = json.loads(
        (session.run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )
    quality_report = json.loads(
        (session.run_dir / "data_quality.json").read_text(
            encoding="utf-8"
        )
    )

    assert pipeline_report["status"] == "FAILED"
    assert pipeline_report["seasons"][0]["season"] == 2023
    assert (
        pipeline_report["seasons"][0]["stages"]["data_quality"]
        == "FAILED"
    )

    assert quality_report["overall_status"] == "FAIL"
    assert quality_report["failed_checks"] == 1
    assert quality_report["seasons"][0]["season"] == 2023
    assert (
        quality_report["seasons"][0]["checks"][1]["name"]
        == "invalid_finished_fixtures"
    )

    assert len(list(tmp_path.iterdir())) == 1



def test_multiple_seasons_preserve_failed_quality_in_one_run(
    tmp_path,
    monkeypatch,
):
    import json
    import pytest
    import run_pipeline

    session = ExecutionSession.create(
        source="api_football",
        mode="full",
        base_dir=tmp_path,
    )

    monkeypatch.setenv("LEAGUE_ID", "39")
    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        lambda *args: None,
    )
    monkeypatch.setattr(
        run_pipeline,
        "create_gold_view",
        lambda: None,
    )

    def fake_quality(
        *,
        run_id=None,
        run_dir=None,
        source=None,
        on_report=None,
    ):
        season = int(run_pipeline.os.environ["SEASON"])
        failed = season == 2023

        report = {
            "overall_status": "FAIL" if failed else "PASS",
            "total_checks": 1,
            "failed_checks": int(failed),
            "checks": [{
                "name": "invalid_finished_fixtures",
                "status": "FAIL" if failed else "PASS",
                "failures": int(failed),
            }],
        }

        if on_report is not None:
            on_report(report)

        if failed:
            raise ValueError("Synthetic Data Quality failure")

        return report

    monkeypatch.setattr(
        run_pipeline,
        "run_data_quality_checks",
        fake_quality,
    )

    monkeypatch.setenv("SEASON", "2022")
    run_pipeline.run_for_season(
        fetch=False,
        session=session,
    )

    monkeypatch.setenv("SEASON", "2023")
    with pytest.raises(
        ValueError,
        match="Synthetic Data Quality failure",
    ):
        run_pipeline.run_for_season(
            fetch=False,
            session=session,
        )

    session.save_reports()

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    assert run_dirs[0] == session.run_dir

    pipeline = json.loads(
        (session.run_dir / "pipeline.json").read_text(
            encoding="utf-8"
        )
    )
    quality = json.loads(
        (session.run_dir / "data_quality.json").read_text(
            encoding="utf-8"
        )
    )

    assert pipeline["status"] == "FAILED"
    assert [s["season"] for s in pipeline["seasons"]] == [
        2022, 2023
    ]
    assert [s["status"] for s in pipeline["seasons"]] == [
        "SUCCESS", "FAILED"
    ]

    assert quality["overall_status"] == "FAIL"
    assert quality["total_checks"] == 2
    assert quality["failed_checks"] == 1
    assert [s["season"] for s in quality["seasons"]] == [
        2022, 2023
    ]
