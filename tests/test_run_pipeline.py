import argparse
import subprocess
from pathlib import Path

import psycopg
import pytest
import sys

import run_pipeline
from run_pipeline import positive_int, run_script, FOOTBALL_DATA_COMPETITION_IDS, ROOT

@pytest.fixture(autouse=True)
def no_report_files(monkeypatch):
    """Keep tests from writing real pipeline reports to the reports folder."""
    monkeypatch.setattr(
        run_pipeline,
        "generate_pipeline_report",
        lambda **kwargs: {"status": "SUCCESS"},
    )

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("39", 39),
        ("2023", 2023),
    ],
)
def test_positive_int_accepts_valid_values(value, expected):
    assert positive_int(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "abc",
        "1.5",
        "",
    ],
)
def test_positive_int_rejects_invalid_values(value):
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int(value)


def test_run_script_executes_subprocess(monkeypatch, caplog):
    import io
    from unittest.mock import MagicMock

    calls = []

    process = MagicMock()
    process.stdout = io.StringIO(
        "Synthetic transformation completed\n"
    )
    process.wait.return_value = 0
    process.__enter__.return_value = process

    def mock_popen(command, **kwargs):
        calls.append({
            "command": command,
            "kwargs": kwargs,
        })
        return process

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    with caplog.at_level("INFO"):
        run_script(
            "src/processing/transform_api_football.py"
        )

    assert len(calls) == 1

    call = calls[0]
    command = call["command"]
    kwargs = call["kwargs"]

    assert command == [
        sys.executable,
        "-u",
        "-m",
        "src.processing.transform_api_football",
    ]

    assert kwargs["cwd"] == ROOT
    assert kwargs["stdout"] == subprocess.PIPE
    assert kwargs["stderr"] == subprocess.STDOUT
    assert kwargs["text"] is True

    assert "Synthetic transformation completed" in caplog.text
    assert "Child process completed" in caplog.text



def test_run_script_logs_failure_and_reraises(
    monkeypatch, caplog
):
    import io
    from unittest.mock import MagicMock

    process = MagicMock()
    process.stdout = io.StringIO(
        "Synthetic loader failure\n"
    )
    process.wait.return_value = 1
    process.__enter__.return_value = process

    def mock_popen(command, **kwargs):
        return process

    monkeypatch.setattr(
        subprocess,
        "Popen",
        mock_popen,
    )

    with caplog.at_level("ERROR"):
        with pytest.raises(
            subprocess.CalledProcessError
        ) as exc_info:
            run_script(
                "src/warehouse/load_to_postgres.py",
                "--source",
                "api_football",
            )

    assert exc_info.value.returncode == 1

    assert "Child process failed" in caplog.text
    assert "exit_code=1" in caplog.text



def test_main_stops_when_a_script_fails(monkeypatch):
    def mock_run_script(script_path):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=[script_path],
        )

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        mock_run_script,
    )

    monkeypatch.setattr(
        run_pipeline,
        "create_gold_view",
        lambda: pytest.fail(
            "Gold view should not be created after a failure"
        ),
    )

    monkeypatch.setattr(
        "sys.argv",
        ["run_pipeline.py", "--league-id", "39", "--season", "2023"],
    )

    with pytest.raises(subprocess.CalledProcessError):
        run_pipeline.main()


def test_main_ensures_bucket_before_others_steps(monkeypatch):
    calls = []

    monkeypatch.setattr(
        run_pipeline,
        "run_script",
        lambda script_path, *args: calls.append(script_path),
    )

    monkeypatch.setattr(run_pipeline, "create_gold_view", lambda: None)
    monkeypatch.setattr(
        run_pipeline,
        "run_data_quality_checks",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        "sys.argv",
        ["run_pipeline.py", "--fetch", "--league-id", "39", "--season", "2023"],
    )

    run_pipeline.main()

    assert calls[0] == "src/storage/ensure_bucket.py"


def test_create_gold_view_propagates_database_error(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    def mock_connect(**kwargs):
        raise psycopg.OperationalError(
            "Database connection failed"
        )

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        mock_connect,
    )

    with pytest.raises(
        psycopg.OperationalError,
        match="Database connection failed",
    ):
        run_pipeline.create_gold_view()


def test_create_gold_view_executes_all_gold_sql_files(monkeypatch, tmp_path):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    (sql_dir / "gold_team_stats.sql").write_text(
        "CREATE OR REPLACE VIEW gold_team_stats AS SELECT 1;",
        encoding="utf-8",
    )
    (sql_dir / "gold_team_recent_form.sql").write_text(
        "CREATE OR REPLACE VIEW gold_team_recent_form AS SELECT 1;",
        encoding="utf-8",
    )

    monkeypatch.setattr(run_pipeline, "ROOT", tmp_path)
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    executed = []

    class FakeCursor:
        def execute(self, statement):
            executed.append(statement)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        lambda **kwargs: FakeConnection(),
    )

    run_pipeline.create_gold_view()

    assert executed == [
        "CREATE OR REPLACE VIEW gold_team_stats AS SELECT 1;",
        "CREATE OR REPLACE VIEW gold_team_recent_form AS SELECT 1;",
    ]

def test_run_data_quality_checks_passes(monkeypatch, tmp_path):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    sql_file = sql_dir / "data_quality_checks.sql"
    sql_file.write_text(
        "SELECT 'duplicate_fixture_ids' AS check_name, 0 AS failures;",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        run_pipeline,
        "ROOT",
        tmp_path,
    )
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    class FakeCursor:
        def execute(self, statement):
            pass

        def fetchone(self):
            return ("duplicate_fixture_ids", 0)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        lambda **kwargs: FakeConnection(),
    )

    run_pipeline.run_data_quality_checks()


def test_run_data_quality_checks_fails_on_invalid_data(
    monkeypatch,
    tmp_path,
):
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()

    sql_file = sql_dir / "data_quality_checks.sql"
    sql_file.write_text(
        "SELECT 'duplicate_fixture_ids' AS check_name, 0 AS failures;",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        run_pipeline,
        "ROOT",
        tmp_path,
    )
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")

    class FakeCursor:
        def execute(self, statement):
            pass

        def fetchone(self):
            return ("duplicate_fixture_ids", 1)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeConnection:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(
        run_pipeline.psycopg,
        "connect",
        lambda **kwargs: FakeConnection(),
    )

    with pytest.raises(ValueError, match="duplicate_fixture_ids"):
        run_pipeline.run_data_quality_checks()

@pytest.mark.parametrize(
    "competition, expected_id",
    [
        ("PD", 2014),
        ("PL", 2021),
        ("BL1", 2002),
        ("SA", 2019),
        ("FL1", 2015),
    ],
)
def test_football_data_competition_ids(competition, expected_id):
    assert FOOTBALL_DATA_COMPETITION_IDS[competition] == expected_id


def test_rejects_unsupported_competition():
    result = subprocess.run(
        [
            sys.executable,
            "run_pipeline.py",
            "--source",
            "football_data",
            "--competition",
            "XYZ",
            "--season",
            "2024",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Unsupported competition: XYZ" in result.stderr


@pytest.mark.parametrize(
    "source,extra_args",
    [
        (
            "api_football",
            ["--league-id", "39"],
        ),
        (
            "football_data",
            ["--competition", "PL"],
        ),
    ],
)

def test_load_only_uses_shared_loader_for_both_sources(
    monkeypatch, source, extra_args
):
    """Both providers must select the shared loading mode."""

    calls = []

    monkeypatch.setenv("SEASON", "2023")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pipeline.py",
            "--load-only",
            "--source",
            source,
            "--season",
            "2023",
            *extra_args,
        ],
    )

    monkeypatch.setattr(
        run_pipeline,
        "run_partial_pipeline",
        lambda mode, source: calls.append((mode, source)),
    )

    run_pipeline.main()

    assert calls == [
        ("loading", source),
    ]

