
"""Test child-process logging without launching real processes."""

import io
import logging
import subprocess
from unittest.mock import MagicMock

import pytest

import run_pipeline


def fake_process(output, exit_code):
    """Create a mock process supporting the context manager."""

    process = MagicMock()
    process.stdout = io.StringIO(output)
    process.wait.return_value = exit_code
    process.__enter__.return_value = process

    return process


def test_child_output_is_logged(monkeypatch, caplog):
    process = fake_process(
        "Silver transformation started\n"
        "Silver transformation completed\n",
        exit_code=0,
    )

    popen = MagicMock(return_value=process)

    monkeypatch.setattr(
        run_pipeline.subprocess,
        "Popen",
        popen,
    )

    with caplog.at_level(logging.INFO):
        run_pipeline.run_script(
            "src/processing/transform_api_football.py"
        )

    assert "Silver transformation started" in caplog.text
    assert "Silver transformation completed" in caplog.text
    assert "Child process completed" in caplog.text

    command = popen.call_args.args[0]

    assert command[:4] == [
        run_pipeline.sys.executable,
        "-u",
        "-m",
        "src.processing.transform_api_football",
    ]


def test_child_receives_loader_arguments(monkeypatch):
    process = fake_process("", exit_code=0)
    popen = MagicMock(return_value=process)

    monkeypatch.setattr(
        run_pipeline.subprocess,
        "Popen",
        popen,
    )

    run_pipeline.run_script(
        "src/warehouse/load_to_postgres.py",
        "--source",
        "football_data",
    )

    command = popen.call_args.args[0]

    assert command == [
        run_pipeline.sys.executable,
        "-u",
        "-m",
        "src.warehouse.load_to_postgres",
        "--source",
        "football_data",
    ]


def test_failed_child_raises_and_logs_error(
    monkeypatch,
    caplog,
):
    process = fake_process(
        "Synthetic loader error\n",
        exit_code=7,
    )

    popen = MagicMock(return_value=process)

    monkeypatch.setattr(
        run_pipeline.subprocess,
        "Popen",
        popen,
    )

    with caplog.at_level(logging.INFO):
        with pytest.raises(
            subprocess.CalledProcessError
        ) as exc_info:
            run_pipeline.run_script(
                "src/warehouse/load_to_postgres.py",
                "--source",
                "api_football",
            )

    assert exc_info.value.returncode == 7
    assert "Synthetic loader error" in caplog.text
    assert "Child process failed" in caplog.text
