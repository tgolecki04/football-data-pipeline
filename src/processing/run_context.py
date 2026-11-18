
"""Shared paths and identifiers for pipeline execution artifacts."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"


def create_run_id() -> str:
    """Create a unique, sortable identifier for one execution."""

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    suffix = uuid4().hex[:8]

    return f"{timestamp}_{suffix}"


def create_run_directory(
    run_id: str | None = None,
    base_dir: Path | None = None,
) -> tuple[str, Path]:
    """Create a new, non-overwriting directory for a pipeline run."""

    root = Path(base_dir) if base_dir is not None else RUNS_DIR

    if run_id is None:
        # Retry only for automatically generated identifiers.
        for _ in range(5):
            candidate = create_run_id()

            try:
                directory = root / candidate
                directory.mkdir(parents=True, exist_ok=False)
                return candidate, directory
            except FileExistsError:
                continue

        raise RuntimeError("Could not create a unique run directory.")

    # Explicit identifiers must be a single safe path component.
    if (
        not run_id
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
        or not all(
            character.isascii()
            and (character.isalnum() or character in "-_")
            for character in run_id
        )
    ):
        raise ValueError("Invalid run_id.")

    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=False)

    return run_id, directory


def write_json_atomic(path: Path, data: dict) -> Path:
    """Write JSON without leaving a partially written destination."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        data,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return path
